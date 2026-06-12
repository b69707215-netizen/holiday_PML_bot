from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, desc
from database import SessionLocal, User, Vacation, UserRole, VacationStatus
from keyboards import teacher_main_menu, cancel_button, vacation_approval
from states import VacationRequest
from datetime import datetime, date
from aiogram.types import CallbackQuery
from config import SECRETARY_IDS

router = Router()

@router.message(F.text == "📋 Мої відпускні дні")
async def show_vacation_days(message: Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Користувача не знайдено. Натисніть /start для реєстрації.")
            return
        
        vacations_result = await session.execute(
            select(Vacation)
            .where(Vacation.user_id == user.id)
            .order_by(desc(Vacation.created_at))
        )
        vacations = vacations_result.scalars().all()
        
        response = (
            f"📊 <b>Інформація про відпустку</b>\n\n"
            f"👤 <b>{user.full_name}</b>\n"
            f"📅 Всього днів: {user.vacation_days_total}\n"
            f"✅ Використано: {user.vacation_days_used}\n"
            f"🎯 Залишилось: {user.vacation_days_remaining}\n\n"
        )
        
        if vacations:
            response += "📋 <b>Історія заявок:</b>\n\n"
            for vac in vacations:
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
                    f"{status_emoji} <b>{vac.start_date.strftime('%d.%m.%Y')} — "
                    f"{vac.end_date.strftime('%d.%m.%Y')}</b>\n"
                    f"   Днів: {vac.days_count} | Статус: {status_text}\n\n"
                )
        else:
            response += "📋 Історія заявок порожня."
        
        await message.answer(response, parse_mode="HTML")

@router.message(F.text == "📝 Подати заявку на відпустку")
async def request_vacation_start(message: Message, state: FSMContext):
    await message.answer(
        "📅 Введіть дату початку відпустки у форматі ДД.ММ.РРРР:\n\n"
        "Приклад: 15.07.2025",
        reply_markup=cancel_button()
    )
    await state.set_state(VacationRequest.start_date)

@router.message(VacationRequest.start_date, F.text == "❌ Скасувати")
async def cancel_vacation_request(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заявку скасовано. Оберіть дію:",
        reply_markup=teacher_main_menu()
    )

@router.message(VacationRequest.start_date)
async def process_start_date(message: Message, state: FSMContext):
    try:
        start_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        if start_date < date.today():
            await message.answer(
                "❌ Дата початку не може бути в минулому. Спробуйте ще раз:"
            )
            return
        
        await state.update_data(start_date=start_date)
        await message.answer(
            "📅 Введіть дату закінчення відпустки у форматі ДД.ММ.РРРР:\n\n"
            "Приклад: 30.07.2025",
            reply_markup=cancel_button()
        )
        await state.set_state(VacationRequest.end_date)
    except ValueError:
        await message.answer(
            "❌ Невірний формат дати. Використовуйте формат ДД.ММ.РРРР (наприклад, 15.07.2025):"
        )

@router.message(VacationRequest.end_date, F.text == "❌ Скасувати")
async def cancel_end_date(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заявку скасовано. Оберіть дію:",
        reply_markup=teacher_main_menu()
    )

@router.message(VacationRequest.end_date)
async def process_end_date(message: Message, state: FSMContext):
    try:
        end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        data = await state.get_data()
        start_date = data["start_date"]
        
        if end_date < start_date:
            await message.answer(
                "❌ Дата закінчення не може бути раніше дати початку. Спробуйте ще раз:"
            )
            return
        
        days_count = (end_date - start_date).days + 1
        
        async with SessionLocal() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer("❌ Користувача не знайдено.")
                return
            
            if days_count > user.vacation_days_remaining:
                await message.answer(
                    f"❌ У вас недостатньо днів відпустки.\n\n"
                    f"Запитано: {days_count} днів\n"
                    f"Доступно: {user.vacation_days_remaining} днів\n\n"
                    "Спробуйте обрати інші дати.",
                    reply_markup=teacher_main_menu()
                )
                await state.clear()
                return
        
        await state.update_data(end_date=end_date, days_count=days_count)
        
        await message.answer(
            f"📋 <b>Підтвердіть заявку:</b>\n\n"
            f"📅 Період: {start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}\n"
            f"📊 Кількість днів: {days_count}\n\n"
            "Відправте «Так» для підтвердження або «Ні» для скасування:",
            parse_mode="HTML",
            reply_markup=cancel_button()
        )
        await state.set_state(VacationRequest.confirm)
        
    except ValueError:
        await message.answer(
            "❌ Невірний формат дати. Використовуйте формат ДД.ММ.РРРР (наприклад, 30.07.2025):"
        )

@router.message(VacationRequest.confirm, F.text == "❌ Скасувати")
async def cancel_confirm(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заявку скасовано. Оберіть дію:",
        reply_markup=teacher_main_menu()
    )

@router.message(VacationRequest.confirm)
async def process_confirm(message: Message, state: FSMContext, bot: Bot):
    if message.text.lower() not in ["так", "yes", "т", "y", "да"]:
        await state.clear()
        await message.answer(
            "❌ Заявку скасовано. Оберіть дію:",
            reply_markup=teacher_main_menu()
        )
        return

    data = await state.get_data()

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Користувача не знайдено.")
            return

        new_vacation = Vacation(
            user_id=user.id,
            start_date=data["start_date"],
            end_date=data["end_date"],
            days_count=data["days_count"],
            status=VacationStatus.PENDING
        )
        session.add(new_vacation)
        await session.commit()

        for secretary_id in SECRETARY_IDS:
            try:
                await bot.send_message(
                    secretary_id,
                    f"📨 <b>Нова заявка на відпустку!</b>\n\n"
                    f"👤 <b>{user.full_name}</b>\n"
                    f"📞 Телефон: {user.phone}\n"
                    f"📅 Період: {data['start_date'].strftime('%d.%m.%Y')} — "
                    f"{data['end_date'].strftime('%d.%m.%Y')}\n"
                    f"📊 Днів: {data['days_count']}",
                    parse_mode="HTML",
                    reply_markup=vacation_approval(new_vacation.id)
                )
            except Exception as e:
                print(f"Failed to notify secretary: {e}")

    await message.answer(
        "✅ Заявку на відпустку успішно надіслано!\n\n"
        "Після підтвердження секретарем ви отримаєте сповіщення.",
        reply_markup=teacher_main_menu()
    )
    await state.clear()
