from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
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

@router.message(F.text == "📨 Новые заявки")
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
                "✅ Нет новых заявок на отпуск.",
                reply_markup=secretary_main_menu()
            )
            return
        
        await message.answer(f"📋 Найдено {len(pending)} заявок на отпуск:")
        
        for vacation, user in pending:
            await message.answer(
                f"📨 <b>Заявка #{vacation.id}</b>\n\n"
                f"👤 <b>{user.full_name}</b>\n"
                f"📞 Телефон: {user.phone}\n"
                f"📅 Период: {vacation.start_date.strftime('%d.%m.%Y')} - "
                f"{vacation.end_date.strftime('%d.%m.%Y')}\n"
                f"📊 Дней: {vacation.days_count}\n"
                f"🎯 Осталось дней: {user.vacation_days_remaining}",
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
            await callback.answer("Заявка уже обработана!")
            return
        
        vacation.status = VacationStatus.APPROVED
        user.vacation_days_used += vacation.days_count
        await session.commit()
        
        # Generate order
        try:
            order_path = await generate_vacation_order(user, vacation)
            
            # Send order to teacher
            document = FSInputFile(order_path)
            await bot.send_document(
                user.telegram_id,
                document,
                caption=f"✅ Ваша заявка на отпуск одобрена!\n\n"
                        f"📅 Период: {vacation.start_date.strftime('%d.%m.%Y')} - "
                        f"{vacation.end_date.strftime('%d.%m.%Y')}"
            )
        except Exception as e:
            await bot.send_message(
                user.telegram_id,
                f"✅ Ваша заявка на отпуск одобрена!\n\n"
                f"📅 Период: {vacation.start_date.strftime('%d.%m.%Y')} - "
                f"{vacation.end_date.strftime('%d.%m.%Y')}\n\n"
                f"⚠️ Ошибка генерации приказа: {str(e)}"
            )
    
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>ОДОБРЕНО</b>",
        parse_mode="HTML"
    )
    await callback.answer("Заявка одобрена!")

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
            await callback.answer("Заявка уже обработана!")
            return
        
        vacation.status = VacationStatus.REJECTED
        await session.commit()
        
        # Notify teacher
        await bot.send_message(
            user.telegram_id,
            f"❌ Ваша заявка на отпуск отклонена.\n\n"
            f"📅 Период: {vacation.start_date.strftime('%d.%m.%Y')} - "
            f"{vacation.end_date.strftime('%d.%m.%Y')}\n\n"
            f"Свяжитесь с секретарем для уточнения."
        )
    
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ОТКЛОНЕНО</b>",
        parse_mode="HTML"
    )
    await callback.answer("Заявка отклонена!")

@router.message(F.text == "👥 Список сотрудников")
async def show_employees(message: Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.role == UserRole.TEACHER)
            .order_by(User.full_name)
        )
        teachers = result.scalars().all()
        
        if not teachers:
            await message.answer("❌ В базе нет учителей.")
            return
        
        response = "👥 <b>Список сотрудников:</b>\n\n"
        
        for i, teacher in enumerate(teachers, 1):
            response += (
                f"{i}. <b>{teacher.full_name}</b>\n"
                f"   📞 {teacher.phone}\n"
                f"   📅 Отпуск: {teacher.vacation_days_remaining}/"  
                f"{teacher.vacation_days_total} дней\n\n"
            )
        
        await message.answer(response, parse_mode="HTML")

@router.message(F.text == "📊 Мониторинг отпусков")
async def show_vacation_monitoring(message: Message):
    async with SessionLocal() as session:
        # Get all approved vacations grouped by month
        result = await session.execute(
            select(Vacation, User)
            .join(User)
            .where(Vacation.status == VacationStatus.APPROVED)
            .order_by(Vacation.start_date)
        )
        approved_vacations = result.all()
        
        # Get statistics
        total_teachers = await session.execute(
            select(func.count(User.id)).where(User.role == UserRole.TEACHER)
        )
        total_count = total_teachers.scalar()
        
        on_vacation_now = 0
        from datetime import date
        today = date.today()
        
        response = (
            f"📊 <b>Мониторинг отпусков</b>\n\n"
            f"👥 Всего учителей: {total_count}\n"
        )
        
        if approved_vacations:
            response += "\n📅 <b>Утвержденные отпуска:</b>\n\n"
            for vacation, user in approved_vacations:
                status = "🏖️ В отпуске" if vacation.start_date <= today <= vacation.end_date else ""
                if status:
                    on_vacation_now += 1
                    
                response += (
                    f"👤 <b>{user.full_name}</b> {status}\n"
                    f"   📅 {vacation.start_date.strftime('%d.%m.%Y')} - "
                    f"{vacation.end_date.strftime('%d.%m.%Y')}\n"
                    f"   📊 {vacation.days_count} дней\n\n"
                )
            
            response += f"\n🏖️ Сейчас в отпуске: {on_vacation_now} чел."
        else:
            response += "\n📅 Утвержденных отпусков нет."
        
        await message.answer(response, parse_mode="HTML")

@router.message(F.text == "📄 Создать приказ")
async def create_order_start(message: Message):
    await message.answer(
        "📄 Выберите тип приказа:",
        reply_markup=order_type_selection()
    )

@router.message(F.text.in_(["🏖️ Отпуск", "🌸 Весняні канікули", "💪 Молодь за здоров'я", 
                              "🛡️ 16 днів проти насильства", "🏕️ Джура"]))
async def select_order_template(message: Message):
    order_type = message.text
    template_map = {
        "🏖️ Отпуск": None,
        "🌸 Весняні канікули": "Весняні канікули 2025.docx",
        "💪 Молодь за здоров'я": "«Молодь за здоров'я» 2025.docx",
        "🛡️ 16 днів проти насильства": "16 днів проти насильства 2025.docx",
        "🏕️ Джура": "Джура 2025.docx"
    }
    
    template = template_map.get(order_type)
    
    if order_type == "🏖️ Отпуск":
        await message.answer(
            "🏖️ Для создания приказа об отпуске используйте функцию «📨 Новые заявки».\n\n"
            "Там можно одобрить заявку и приказ будет сгенерирован автоматически.",
            reply_markup=secretary_main_menu()
        )
        return
    
    await message.answer(
        f"📄 Выбран тип: {order_type}\n"
        f"📝 Шаблон: {template}\n\n"
        "Эта функция в разработке. Сейчас можно автоматически генерировать\n"
        "только приказы об отпуске через меню «📨 Новые заявки».",
        reply_markup=secretary_main_menu()
    )

@router.message(F.text == "🔍 Найти учителя по ФИО")
async def search_teacher_start(message: Message, state: FSMContext):
    await message.answer(
        "🔍 Введите ФИО учителя для поиска:\n\n"
        "Пример: Иванов Иван Иванович\n"
        "Можно вводить частично (например, только фамилию)",
        reply_markup=cancel_button()
    )
    await state.set_state(SearchTeacher.full_name)

@router.message(SearchTeacher.full_name, F.text == "❌ Отмена")
async def cancel_search(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Поиск отменен. Выберите действие:",
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
                f"❌ Учителя с ФИО «{message.text}» не найдены.\n\n"
                "Попробуйте другой запрос или проверьте написание.",
                reply_markup=cancel_button()
            )
            return

        await state.clear()

        if len(teachers) == 1:
            teacher = teachers[0]
            await show_teacher_details(message, teacher)
        else:
            await message.answer(
                f"🔍 Найдено {len(teachers)} учителей:\n\n"
                "Введите точное ФИО для просмотра деталей:"
            )
            for teacher in teachers:
                status_emoji = "🟢" if teacher.vacation_days_remaining > 0 else "🔴"
                await message.answer(
                    f"👤 <b>{teacher.full_name}</b>\n"
                    f"   📞 {teacher.phone}\n"
                    f"   {status_emoji} Отпуск: {teacher.vacation_days_remaining}/"
                    f"{teacher.vacation_days_total} дней",
                    parse_mode="HTML"
                )

async def show_teacher_details(message: Message, teacher: User):
    """Show detailed vacation info for a teacher."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Vacation)
            .where(Vacation.user_id == teacher.id)
            .order_by(desc(Vacation.created_at))
        )
        vacations = result.scalars().all()

        response = (
            f"📋 <b>ПОЛНАЯ ИНФОРМАЦИЯ</b>\n"
            f"{'=' * 30}\n\n"
            f"👤 <b>{teacher.full_name}</b>\n"
            f"📞 Телефон: {teacher.phone}\n"
            f"🆔 ID: {teacher.telegram_id}\n\n"
            f"📊 <b>ОТПУСКНЫЕ ДНИ:</b>\n"
            f"   Всего положено: {teacher.vacation_days_total} дней\n"
            f"   ✅ Использовано: {teacher.vacation_days_used} дней\n"
            f"   🎯 <b>Осталось: {teacher.vacation_days_remaining} дней</b>\n\n"
        )

        if vacations:
            response += f"📅 <b>ИСТОРИЯ ОТПУСКОВ ({len(vacations)} записей):</b>\n\n"
            for i, vac in enumerate(vacations, 1):
                status_emoji = {
                    VacationStatus.PENDING: "⏳",
                    VacationStatus.APPROVED: "✅",
                    VacationStatus.REJECTED: "❌"
                }.get(vac.status, "❓")

                status_text = {
                    VacationStatus.PENDING: "На рассмотрении",
                    VacationStatus.APPROVED: "Одобрено",
                    VacationStatus.REJECTED: "Отклонено"
                }.get(vac.status, "Неизвестно")

                response += (
                    f"{i}. {status_emoji} <b>{vac.start_date.strftime('%d.%m.%Y')} - "
                    f"{vac.end_date.strftime('%d.%m.%Y')}</b>\n"
                    f"   📊 Дней: {vac.days_count}\n"
                    f"   📌 Статус: {status_text}\n\n"
                )
        else:
            response += "📅 История отпусков: нет записей"

        await message.answer(response, parse_mode="HTML", reply_markup=secretary_main_menu())

@router.message(F.text == "📢 Рассылка PML")
async def start_pml_broadcast(message: Message, state: FSMContext):
    """Start PML broadcast - only for secretary."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user or user.role != UserRole.SECRETARY:
            await message.answer("❌ Эта функция доступна только секретарю.")
            return

        # Count subscribed users
        subscribed_result = await session.execute(
            select(func.count(User.id)).where(User.pml_subscribed == 1)
        )
        subscribed_count = subscribed_result.scalar()

        await message.answer(
            f"📢 <b>Создание рассылки PML</b>\n\n"
            f"👥 Подписано пользователей: {subscribed_count}\n\n"
            f"Введите текст сообщения для рассылки:",
            parse_mode="HTML",
            reply_markup=cancel_button()
        )
        await state.set_state(PMLBroadcast.message_text)


@router.message(PMLBroadcast.message_text, F.text == "❌ Отмена")
async def cancel_pml_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Рассылка отменена. Выберите действие:",
        reply_markup=secretary_main_menu()
    )


@router.message(PMLBroadcast.message_text)
async def process_pml_message(message: Message, state: FSMContext):
    """Save message text and ask for confirmation."""
    await state.update_data(message_text=message.text)

    await message.answer(
        f"📢 <b>Предпросмотр сообщения:</b>\n\n"
        f"{message.text}\n\n"
        f"Подтвердите отправку:",
        parse_mode="HTML",
        reply_markup=pml_broadcast_confirm()
    )
    await state.set_state(PMLBroadcast.confirm)


@router.message(PMLBroadcast.confirm, F.text == "✅ Отправить рассылку")
async def send_pml_broadcast(message: Message, state: FSMContext, bot: Bot):
    """Send broadcast to all subscribed users."""
    data = await state.get_data()
    message_text = data.get("message_text")

    async with SessionLocal() as session:
        # Get sender
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        sender = result.scalar_one_or_none()

        # Save broadcast to database
        broadcast = BroadcastMessage(
            message_text=message_text,
            sender_id=sender.id
        )
        session.add(broadcast)

        # Get all subscribed users
        result = await session.execute(
            select(User).where(User.pml_subscribed == 1)
        )
        subscribed_users = result.scalars().all()

        sent_count = 0
        failed_count = 0

        # Send messages
        for user in subscribed_users:
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"📢 <b>Сообщение от администрации:</b>\n\n{message_text}",
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Failed to send to {user.telegram_id}: {e}")

        broadcast.sent_count = sent_count
        await session.commit()

    await message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: {sent_count}\n"
        f"❌ Не доставлено: {failed_count}",
        parse_mode="HTML",
        reply_markup=secretary_main_menu()
    )
    await state.clear()


@router.message(PMLBroadcast.confirm, F.text == "❌ Отмена")
async def cancel_pml_confirm(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Рассылка отменена. Выберите действие:",
        reply_markup=secretary_main_menu()
    )


@router.message(F.text == "❌ Отмена")
async def cancel_action(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Действие отменено. Выберите действие:",
        reply_markup=secretary_main_menu()
    )

# ==================== HANDLERS FOR VACATION ORDERS ====================

@router.message(F.text == "📄 Создать приказ")
@router.message(Command("create_vacation_order"))
async def start_vacation_order_creation(message: Message, state: FSMContext):
    """Начало создания отпускного приказа"""
    await message.answer(
        "📄 <b>Создание отпускного приказа</b>\n\n"
        "Введите ФИО сотрудника:",
        parse_mode="HTML"
    )
    await state.set_state(VacationOrderState.employee_name)

@router.message(VacationOrderState.employee_name)
async def process_employee_name(message: Message, state: FSMContext):
    """Обработка ФИО сотрудника"""
    await state.update_data(employee_name=message.text)
    await message.answer(
        f"✅ ФИО: {message.text}\n\n"
        "Введите дату начала отпуска (ДД.ММ.ГГГГ):"
    )
    await state.set_state(VacationOrderState.start_date)

@router.message(VacationOrderState.start_date)
async def process_start_date(message: Message, state: FSMContext):
    """Обработка даты начала отпуска"""
    await state.update_data(start_date=message.text)
    await message.answer(
        f"✅ Дата начала: {message.text}\n\n"
        "Введите дату окончания отпуска (ДД.ММ.ГГГГ):"
    )
    await state.set_state(VacationOrderState.end_date)

@router.message(VacationOrderState.end_date)
async def process_end_date(message: Message, state: FSMContext):
    """Обработка даты окончания отпуска"""
    await state.update_data(end_date=message.text)
    
    # Предлагаем варианты типа отпуска
    keyboard = {
        "inline_keyboard": [
            [{"text": "Ежегодный", "callback_data": "vac_type:ежегодный"}],
            [{"text": "Дополнительный", "callback_data": "vac_type:дополнительный"}],
            [{"text": "Учебный", "callback_data": "vac_type:учебный"}],
            [{"text": "Без сохранения зарплаты", "callback_data": "vac_type:без_зарплаты"}]
        ]
    }
    
    await message.answer(
        f"✅ Дата окончания: {message.text}\n\n"
        "Выберите тип отпуска:",
        reply_markup=keyboard
    )
    await state.set_state(VacationOrderState.vacation_type)

@router.callback_query(F.data.startswith("vac_type:"))
async def process_vacation_type(callback: CallbackQuery, state: FSMContext):
    """Обработка типа отпуска"""
    vacation_type = callback.data.split(":")[1]
    await state.update_data(vacation_type=vacation_type)
    
    await callback.message.edit_text(
        f"✅ Тип отпуска: {vacation_type}\n\n"
        "Введите причину отпуска (или нажмите Пропустить):"
    )
    await state.set_state(VacationOrderState.reason)
    await callback.answer()

@router.message(VacationOrderState.reason)
async def process_reason(message: Message, state: FSMContext):
    """Обработка причины отпуска"""
    reason = message.text if message.text.lower() != "пропустить" else ""
    await state.update_data(reason=reason)
    
    # Показываем сводку данных
    data = await state.get_data()
    
    summary = (
        f"📄 <b>Сводка данных приказа</b>\n\n"
        f"👤 Сотрудник: {data['employee_name']}\n"
        f"📅 Начало: {data['start_date']}\n"
        f"📅 Окончание: {data['end_date']}\n"
        f"🎯 Тип: {data['vacation_type']}\n"
        f"📝 Причина: {reason if reason else 'Не указана'}\n\n"
        f"✅ Создать приказ?"
    )
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "✅ Создать", "callback_data": "vac_order:create"}],
            [{"text": "❌ Отмена", "callback_data": "vac_order:cancel"}]
        ]
    }
    
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(VacationOrderState.confirm)

@router.callback_query(F.data == "vac_order:create")
async def create_vacation_order(callback: CallbackQuery, state: FSMContext):
    """Создание отпускного приказа"""
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
            f"✅ <b>Приказ создан!</b>\n\n"
            f"📄 Текст приказа:\n\n"
            f"<pre>{order_text}</pre>\n\n"
            f"💡 Приказ будет добавлен в CRM систему",
            parse_mode="HTML"
        )
        
        # TODO: Сохранить приказ в CRM систему
        # await save_order_to_crm(order_text, data)
        
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания приказа</b>\n\n"
            f"🔍 {result['error']}",
            parse_mode="HTML"
        )
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "vac_order:cancel")
async def cancel_vacation_order(callback: CallbackQuery, state: FSMContext):
    """Отмена создания приказа"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Создание приказа отменено",
        reply_markup=secretary_main_menu()
    )
    await callback.answer()

@router.message(Command("recent_documents"))
async def show_recent_documents(message: Message):
    """Показать недавно сохраненные документы из CRM"""
    vacation_creator = get_vacation_creator()
    documents = await vacation_creator.get_recent_documents(limit=10)
    
    if not documents:
        await message.answer(
            "📄 <b>Недавно сохраненные документы</b>\n\n"
            "❌ Документы не найдены",
            parse_mode="HTML"
        )
        return
    
    message_text = "📄 <b>Недавно сохраненные документы:</b>\n\n"
    
    for i, doc in enumerate(documents, 1):
        message_text += (
            f"{i}. <b>{doc['filename']}</b>\n"
            f"📅 {doc['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"📊 {doc['size'] // 1024} КБ\n\n"
        )
    
    await message.answer(message_text, parse_mode="HTML")
