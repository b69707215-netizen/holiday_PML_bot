from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, desc, func
from database import SessionLocal, User, Vacation, Order, BroadcastMessage, UserRole, VacationStatus
from keyboards import secretary_main_menu, order_type_selection, vacation_approval, cancel_button, pml_broadcast_confirm
from services.doc_generator import generate_vacation_order, generate_order_from_template
from services.crm_integration import get_vacation_creator
from states import SearchTeacher, PMLBroadcast, VacationOrderState
import os

router = Router()

@router.message(F.text == "📨 Нові заявки")
async def show_pending_vacations(message: Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Vacation, User)
            .join(User)
            .where(Vacation.status == VacationStatus.PENDING)
            .order_by(desc(Vacation.created_at))
        )
        pending = result.all()
        
        if not pending:
            await message.answer(
                "✅ Немає нових заявок на відпустку.",
                reply_markup=secretary_main_menu()
            )
            return
        
        await message.answer(f"📋 Знайдено {len(pending)} заявок на відпустку:")
        
        for vacation, user in pending:
            await message.answer(
                f"📨 <b>Заявка #{vacation.id}</b>\n\n"
                f"👤 <b>{user.full_name}</b>\n"
                f"📞 Телефон: {user.phone}\n"
                f"📅 Період: {vacation.start_date.strftime('%d.%m.%Y')} — "
                f"{vacation.end_date.strftime('%d.%m.%Y')}\n"
                f"📊 Днів: {vacation.days_count}\n"
                f"🎯 Залишилось днів: {user.vacation_days_remaining}",
                parse_mode="HTML",
                reply_markup=vacation_approval(vacation.id)
            )

@router.callback_query(F.data.startswith("approve_vacation:"))
async def approve_vacation(callback: CallbackQuery, bot: Bot):
    vacation_id = int(callback.data.split(":")[1])
    
    async with SessionLocal() as session:
        result = await session.execute(
            select(Vacation, User)
            .join(User)
            .where(Vacation.id == vacation_id)
        )
        vacation, user = result.one()
        
        if vacation.status != VacationStatus.PENDING:
            await callback.answer("Заявку вже оброблено!")
            return
        
        vacation.status = VacationStatus.APPROVED
        user.vacation_days_used += vacation.days_count
        await session.commit()
        
        try:
            order_path = await generate_vacation_order(user, vacation)
            document = FSInputFile(order_path)
            await bot.send_document(
                user.telegram_id,
                document,
                caption=f"✅ Вашу заявку на відпустку схвалено!\n\n"
                        f"📅 Період: {vacation.start_date.strftime('%d.%m.%Y')} — "
                        f"{vacation.end_date.strftime('%d.%m.%Y')}"
            )
        except Exception as e:
            await bot.send_message(
                user.telegram_id,
                f"✅ Вашу заявку на відпустку схвалено!\n\n"
                f"📅 Період: {vacation.start_date.strftime('%d.%m.%Y')} — "
                f"{vacation.end_date.strftime('%d.%m.%Y')}\n\n"
                f"⚠️ Помилка генерації наказу: {str(e)}"
            )
    
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>СХВАЛЕНО</b>",
        parse_mode="HTML"
    )
    await callback.answer("Заявку схвалено!")

@router.callback_query(F.data.startswith("reject_vacation:"))
async def reject_vacation(callback: CallbackQuery, bot: Bot):
    vacation_id = int(callback.data.split(":")[1])
    
    async with SessionLocal() as session:
        result = await session.execute(
            select(Vacation, User)
            .join(User)
            .where(Vacation.id == vacation_id)
        )
        vacation, user = result.one()
        
        if vacation.status != VacationStatus.PENDING:
            await callback.answer("Заявку вже оброблено!")
            return
        
        vacation.status = VacationStatus.REJECTED
        await session.commit()
        
        await bot.send_message(
            user.telegram_id,
            f"❌ Вашу заявку на відпустку відхилено.\n\n"
            f"📅 Період: {vacation.start_date.strftime('%d.%m.%Y')} — "
            f"{vacation.end_date.strftime('%d.%m.%Y')}\n\n"
            f"Зв'яжіться з секретарем для уточнення."
        )
    
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ВІДХИЛЕНО</b>",
        parse_mode="HTML"
    )
    await callback.answer("Заявку відхилено!")

@router.message(F.text == "👥 Список співробітників")
async def show_employees(message: Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.role == UserRole.TEACHER)
            .order_by(User.full_name)
        )
        teachers = result.scalars().all()
        
        if not teachers:
            await message.answer("❌ В базі немає вчителів.")
            return
        
        response = "👥 <b>Список співробітників:</b>\n\n"
        
        for i, teacher in enumerate(teachers, 1):
            response += (
                f"{i}. <b>{teacher.full_name}</b>\n"
                f"   📞 {teacher.phone}\n"
                f"   📅 Відпустка: {teacher.vacation_days_remaining}/"
                f"{teacher.vacation_days_total} днів\n\n"
            )
        
        await message.answer(response, parse_mode="HTML")

@router.message(F.text == "📊 Моніторинг відпусток")
async def show_vacation_monitoring(message: Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Vacation, User)
            .join(User)
            .where(Vacation.status == VacationStatus.APPROVED)
            .order_by(Vacation.start_date)
        )
        approved_vacations = result.all()
        
        total_teachers = await session.execute(
            select(func.count(User.id)).where(User.role == UserRole.TEACHER)
        )
        total_count = total_teachers.scalar()
        
        on_vacation_now = 0
        from datetime import date
        today = date.today()
        
        response = (
            f"📊 <b>Моніторинг відпусток</b>\n\n"
            f"👥 Всього вчителів: {total_count}\n"
        )
        
        if approved_vacations:
            response += "\n📅 <b>Затверджені відпустки:</b>\n\n"
            for vacation, user in approved_vacations:
                status = "🏖️ У відпустці" if vacation.start_date <= today <= vacation.end_date else ""
                if status:
                    on_vacation_now += 1
                    
                response += (
                    f"👤 <b>{user.full_name}</b> {status}\n"
                    f"   📅 {vacation.start_date.strftime('%d.%m.%Y')} — "
                    f"{vacation.end_date.strftime('%d.%m.%Y')}\n"
                    f"   📊 {vacation.days_count} днів\n\n"
                )
            
            response += f"\n🏖️ Зараз у відпустці: {on_vacation_now} осіб."
        else:
            response += "\n📅 Затверджених відпусток немає."
        
        await message.answer(response, parse_mode="HTML")

@router.message(F.text == "📄 Створити наказ")
async def create_order_start(message: Message):
    await message.answer(
        "📄 Оберіть тип наказу:",
        reply_markup=order_type_selection()
    )

@router.message(F.text.in_(["🏖️ Відпустка", "🌸 Весняні канікули", "💪 Молодь за здоров'я",
                              "🛡️ 16 днів проти насильства", "🏕️ Джура"]))
async def select_order_template(message: Message):
    order_type = message.text
    template_map = {
        "🏖️ Відпустка": None,
        "🌸 Весняні канікули": "Весняні канікули 2025.docx",
        "💪 Молодь за здоров'я": "«Молодь за здоров'я» 2025.docx",
        "🛡️ 16 днів проти насильства": "16 днів проти насильства 2025.docx",
        "🏕️ Джура": "Джура 2025.docx"
    }
    
    template = template_map.get(order_type)
    
    if order_type == "🏖️ Відпустка":
        await message.answer(
            "🏖️ Для створення наказу про відпустку використовуйте функцію «📨 Нові заявки».\n\n"
            "Там можна схвалити заявку і наказ згенерується автоматично.",
            reply_markup=secretary_main_menu()
        )
        return
    
    if template:
        try:
            order_path = await generate_order_from_template(template, {})
            document = FSInputFile(order_path)
            await message.answer_document(
                document,
                caption=f"📄 Наказ: {order_type}\n✅ Документ сформовано з шаблону.",
                reply_markup=secretary_main_menu()
            )
        except Exception as e:
            await message.answer(
                f"❌ Помилка генерації наказу: {str(e)}\n\n"
                "Переконайтеся, що шаблон є в папці з документами.",
                reply_markup=secretary_main_menu()
            )
    else:
        await message.answer(
            f"⚠️ Шаблон для «{order_type}» не знайдено.",
            reply_markup=secretary_main_menu()
        )

@router.message(F.text == "🔍 Знайти вчителя за ПІБ")
async def search_teacher_start(message: Message, state: FSMContext):
    await message.answer(
        "🔍 Введіть ПІБ вчителя для пошуку:\n\n"
        "Приклад: Іванenko Іван Іванович\n"
        "Можна вводити частково (наприклад, лише прізвище)",
        reply_markup=cancel_button()
    )
    await state.set_state(SearchTeacher.full_name)

@router.message(SearchTeacher.full_name, F.text == "❌ Скасувати")
async def cancel_search(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Пошук скасовано. Оберіть дію:",
        reply_markup=secretary_main_menu()
    )

@router.message(SearchTeacher.full_name)
async def process_search_teacher(message: Message, state: FSMContext):
    search_query = message.text.strip().lower()

    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.role == UserRole.TEACHER)
            .where(User.full_name.ilike(f"%{search_query}%"))
            .order_by(User.full_name)
        )
        teachers = result.scalars().all()

        if not teachers:
            await message.answer(
                f"❌ Вчителів з ПІБ «{message.text}» не знайдено.\n\n"
                "Спробуйте інший запит або перевірте написання.",
                reply_markup=cancel_button()
            )
            return

        await state.clear()

        if len(teachers) == 1:
            teacher = teachers[0]
            await show_teacher_details(message, teacher)
        else:
            await message.answer(
                f"🔍 Знайдено {len(teachers)} вчителів:\n\n"
                "Введіть точне ПІБ для перегляду деталей:"
            )
            for teacher in teachers:
                status_emoji = "🟢" if teacher.vacation_days_remaining > 0 else "🔴"
                await message.answer(
                    f"👤 <b>{teacher.full_name}</b>\n"
                    f"   📞 {teacher.phone}\n"
                    f"   {status_emoji} Відпустка: {teacher.vacation_days_remaining}/"
                    f"{teacher.vacation_days_total} днів",
                    parse_mode="HTML"
                )

async def show_teacher_details(message: Message, teacher: User):
    """Показати детальну інформацію про відпустку вчителя."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Vacation)
            .where(Vacation.user_id == teacher.id)
            .order_by(desc(Vacation.created_at))
        )
        vacations = result.scalars().all()

        response = (
            f"📋 <b>ПОВНА ІНФОРМАЦІЯ</b>\n"
            f"{'═' * 30}\n\n"
            f"👤 <b>{teacher.full_name}</b>\n"
            f"📞 Телефон: {teacher.phone}\n"
            f"🆔 ID: {teacher.telegram_id}\n\n"
            f"📊 <b>ВІДПУСКНІ ДНІ:</b>\n"
            f"   Всього належить: {teacher.vacation_days_total} днів\n"
            f"   ✅ Використано: {teacher.vacation_days_used} днів\n"
            f"   🎯 <b>Залишилось: {teacher.vacation_days_remaining} днів</b>\n\n"
        )

        if vacations:
            response += f"📅 <b>ІСТОРІЯ ВІДПУСТОК ({len(vacations)} записів):</b>\n\n"
            for i, vac in enumerate(vacations, 1):
                status_emoji = {
                    VacationStatus.PENDING: "⏳",
                    VacationStatus.APPROVED: "✅",
                    VacationStatus.REJECTED: "❌"
                }.get(vac.status, "❓")

                status_text = {
                    VacationStatus.PENDING: "На розгляді",
                    VacationStatus.APPROVED: "Схвалено",
                    VacationStatus.REJECTED: "Відхилено"
                }.get(vac.status, "Невідомо")

                response += (
                    f"{i}. {status_emoji} <b>{vac.start_date.strftime('%d.%m.%Y')} — "
                    f"{vac.end_date.strftime('%d.%m.%Y')}</b>\n"
                    f"   📊 Днів: {vac.days_count}\n"
                    f"   📌 Статус: {status_text}\n\n"
                )
        else:
            response += "📅 Історія відпусток: записів немає"

        await message.answer(response, parse_mode="HTML", reply_markup=secretary_main_menu())

@router.message(F.text == "📢 Розсилка PML")
async def start_pml_broadcast(message: Message, state: FSMContext):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user or user.role != UserRole.SECRETARY:
            await message.answer("❌ Ця функція доступна лише секретарю.")
            return

        subscribed_result = await session.execute(
            select(func.count(User.id)).where(User.pml_subscribed == 1)
        )
        subscribed_count = subscribed_result.scalar()

        await message.answer(
            f"📢 <b>Створення розсилки PML</b>\n\n"
            f"👥 Підписано користувачів: {subscribed_count}\n\n"
            f"Введіть текст повідомлення для розсилки:",
            parse_mode="HTML",
            reply_markup=cancel_button()
        )
        await state.set_state(PMLBroadcast.message_text)


@router.message(PMLBroadcast.message_text, F.text == "❌ Скасувати")
async def cancel_pml_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Розсилку скасовано. Оберіть дію:",
        reply_markup=secretary_main_menu()
    )


@router.message(PMLBroadcast.message_text)
async def process_pml_message(message: Message, state: FSMContext):
    await state.update_data(message_text=message.text)

    await message.answer(
        f"📢 <b>Попередній перегляд повідомлення:</b>\n\n"
        f"{message.text}\n\n"
        f"Підтвердіть надсилання:",
        parse_mode="HTML",
        reply_markup=pml_broadcast_confirm()
    )
    await state.set_state(PMLBroadcast.confirm)


@router.message(PMLBroadcast.confirm, F.text == "✅ Надіслати розсилку")
async def send_pml_broadcast(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    message_text = data.get("message_text")

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        sender = result.scalar_one_or_none()

        broadcast = BroadcastMessage(
            message_text=message_text,
            sender_id=sender.id
        )
        session.add(broadcast)

        result = await session.execute(
            select(User).where(User.pml_subscribed == 1)
        )
        subscribed_users = result.scalars().all()

        sent_count = 0
        failed_count = 0

        for user in subscribed_users:
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"📢 <b>Повідомлення від адміністрації:</b>\n\n{message_text}",
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Failed to send to {user.telegram_id}: {e}")

        broadcast.sent_count = sent_count
        await session.commit()

    await message.answer(
        f"✅ <b>Розсилку завершено!</b>\n\n"
        f"📤 Надіслано: {sent_count}\n"
        f"❌ Не доставлено: {failed_count}",
        parse_mode="HTML",
        reply_markup=secretary_main_menu()
    )
    await state.clear()


@router.message(PMLBroadcast.confirm, F.text == "❌ Скасувати")
async def cancel_pml_confirm(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Розсилку скасовано. Оберіть дію:",
        reply_markup=secretary_main_menu()
    )


@router.message(F.text == "❌ Скасувати")
async def cancel_action(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Дію скасовано. Оберіть дію:",
        reply_markup=secretary_main_menu()
    )

# ==================== HANDLERS FOR VACATION ORDERS ====================

@router.message(Command("create_vacation_order"))
async def start_vacation_order_creation(message: Message, state: FSMContext):
    """Початок створення наказу про відпустку"""
    await message.answer(
        "📄 <b>Створення наказу про відпустку</b>\n\n"
        "Введіть ПІБ співробітника:",
        parse_mode="HTML"
    )
    await state.set_state(VacationOrderState.employee_name)

@router.message(VacationOrderState.employee_name)
async def process_employee_name(message: Message, state: FSMContext):
    await state.update_data(employee_name=message.text)
    await message.answer(
        f"✅ ПІБ: {message.text}\n\n"
        "Введіть дату початку відпустки (ДД.ММ.РРРР):"
    )
    await state.set_state(VacationOrderState.start_date)

@router.message(VacationOrderState.start_date)
async def process_start_date(message: Message, state: FSMContext):
    await state.update_data(start_date=message.text)
    await message.answer(
        f"✅ Дата початку: {message.text}\n\n"
        "Введіть дату закінчення відпустки (ДД.ММ.РРРР):"
    )
    await state.set_state(VacationOrderState.end_date)

@router.message(VacationOrderState.end_date)
async def process_end_date(message: Message, state: FSMContext):
    await state.update_data(end_date=message.text)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Щорічна", callback_data="vac_type:щорічна")],
            [InlineKeyboardButton(text="Додаткова", callback_data="vac_type:додаткова")],
            [InlineKeyboardButton(text="Навчальна", callback_data="vac_type:навчальна")],
            [InlineKeyboardButton(text="Без збереження зарплати", callback_data="vac_type:без_зарплати")]
        ]
    )
    
    await message.answer(
        f"✅ Дата закінчення: {message.text}\n\n"
        "Оберіть тип відпустки:",
        reply_markup=keyboard
    )
    await state.set_state(VacationOrderState.vacation_type)

@router.callback_query(F.data.startswith("vac_type:"))
async def process_vacation_type(callback: CallbackQuery, state: FSMContext):
    vacation_type = callback.data.split(":")[1]
    await state.update_data(vacation_type=vacation_type)
    
    await callback.message.edit_text(
        f"✅ Тип відпустки: {vacation_type}\n\n"
        "Введіть причину відпустки (або напишіть «Пропустити»):"
    )
    await state.set_state(VacationOrderState.reason)
    await callback.answer()

@router.message(VacationOrderState.reason)
async def process_reason(message: Message, state: FSMContext):
    reason = message.text if message.text.lower() not in ["пропустити", "пропустить", "skip"] else ""
    await state.update_data(reason=reason)
    
    data = await state.get_data()
    
    summary = (
        f"📄 <b>Зведення даних наказу</b>\n\n"
        f"👤 Співробітник: {data['employee_name']}\n"
        f"📅 Початок: {data['start_date']}\n"
        f"📅 Закінчення: {data['end_date']}\n"
        f"🎯 Тип: {data['vacation_type']}\n"
        f"📝 Причина: {reason if reason else 'Не вказана'}\n\n"
        f"✅ Створити наказ?"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Створити", callback_data="vac_order:create")],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="vac_order:cancel")]
        ]
    )
    
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(VacationOrderState.confirm)

@router.callback_query(F.data == "vac_order:create")
async def create_vacation_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    vacation_creator = get_vacation_creator()
    result = await vacation_creator.create_vacation_order(
        employee_name=data['employee_name'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        vacation_type=data['vacation_type'],
        reason=data.get('reason', '')
    )
    
    if result['success']:
        order_text = result['order_text']
        
        await callback.message.edit_text(
            f"✅ <b>Наказ створено!</b>\n\n"
            f"📄 Текст наказу:\n\n"
            f"<pre>{order_text}</pre>\n\n"
            f"💡 Наказ буде додано до CRM системи",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Помилка створення наказу</b>\n\n"
            f"🔍 {result['error']}",
            parse_mode="HTML"
        )
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "vac_order:cancel")
async def cancel_vacation_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Створення наказу скасовано")
    await callback.answer()

@router.message(Command("recent_documents"))
async def show_recent_documents(message: Message):
    """Показати нещодавно збережені документи з CRM"""
    vacation_creator = get_vacation_creator()
    documents = await vacation_creator.get_recent_documents(limit=10)
    
    if not documents:
        await message.answer(
            "📄 <b>Нещодавно збережені документи</b>\n\n"
            "❌ Документи не знайдено",
            parse_mode="HTML"
        )
        return
    
    message_text = "📄 <b>Нещодавно збережені документи:</b>\n\n"
    
    for i, doc in enumerate(documents, 1):
        message_text += (
            f"{i}. <b>{doc['filename']}</b>\n"
            f"📅 {doc['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"📊 {doc['size'] // 1024} КБ\n\n"
        )
    
    await message.answer(message_text, parse_mode="HTML")
