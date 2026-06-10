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

@router.message(F.text == "📋 Мои отпускные дни")
async def show_vacation_days(message: Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Пользователь не найден. Нажмите /start для регистрации.")
            return
        
        # Get vacation history
        vacations_result = await session.execute(
            select(Vacation)
            .where(Vacation.user_id == user.id)
            .order_by(desc(Vacation.created_at))
        )
        vacations = vacations_result.scalars().all()
        
        response = (
            f"📊 <b>Информация об отпуске</b>\n\n"
            f"👤 <b>{user.full_name}</b>\n"
            f"📅 Всего дней: {user.vacation_days_total}\n"
            f"✅ Использовано: {user.vacation_days_used}\n"
            f"🎯 Осталось: {user.vacation_days_remaining}\n\n"
        )
        
        if vacations:
            response += "📋 <b>История заявок:</b>\n\n"
            for vac in vacations:
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
                    f"{status_emoji} <b>{vac.start_date.strftime('%d.%m.%Y')} - "
                    f"{vac.end_date.strftime('%d.%m.%Y')}</b>\n"
                    f"   Дней: {vac.days_count} | Статус: {status_text}\n\n"
                )
        else:
            response += "📋 История заявок пуста."
        
        await message.answer(response, parse_mode="HTML")

@router.message(F.text == "📝 Подать заявку на отпуск")
async def request_vacation_start(message: Message, state: FSMContext):
    await message.answer(
        "📅 Введите дату начала отпуска в формате ДД.ММ.ГГГГ:\n\n"
        "Пример: 15.07.2025",
        reply_markup=cancel_button()
    )
    await state.set_state(VacationRequest.start_date)

@router.message(VacationRequest.start_date, F.text == "❌ Отмена")
async def cancel_vacation_request(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заявка отменена. Выберите действие:",
        reply_markup=teacher_main_menu()
    )

@router.message(VacationRequest.start_date)
async def process_start_date(message: Message, state: FSMContext):
    try:
        start_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        if start_date < date.today():
            await message.answer(
                "❌ Дата начала не может быть в прошлом. Попробуйте снова:"
            )
            return
        
        await state.update_data(start_date=start_date)
        await message.answer(
            "📅 Введите дату окончания отпуска в формате ДД.ММ.ГГГГ:\n\n"
            "Пример: 30.07.2025",
            reply_markup=cancel_button()
        )
        await state.set_state(VacationRequest.end_date)
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ (например, 15.07.2025):"
        )

@router.message(VacationRequest.end_date, F.text == "❌ Отмена")
async def cancel_end_date(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заявка отменена. Выберите действие:",
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
                "❌ Дата окончания не может быть раньше даты начала. Попробуйте снова:"
            )
            return
        
        days_count = (end_date - start_date).days + 1
        
        async with SessionLocal() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer("❌ Пользователь не найден.")
                return
            
            if days_count > user.vacation_days_remaining:
                await message.answer(
                    f"❌ У вас недостаточно дней отпуска.\n\n"
                    f"Запрошено: {days_count} дней\n"
                    f"Доступно: {user.vacation_days_remaining} дней\n\n"
                    "Попробуйте выбрать другие даты.",
                    reply_markup=teacher_main_menu()
                )
                await state.clear()
                return
        
        await state.update_data(end_date=end_date, days_count=days_count)
        
        await message.answer(
            f"📋 <b>Подтвердите заявку:</b>\n\n"
            f"📅 Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n"
            f"📊 Количество дней: {days_count}\n\n"
            "Отправьте «Да» для подтверждения или «Нет» для отмены:",
            parse_mode="HTML",
            reply_markup=cancel_button()
        )
        await state.set_state(VacationRequest.confirm)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ (например, 30.07.2025):"
        )

@router.message(VacationRequest.confirm, F.text == "❌ Отмена")
async def cancel_confirm(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заявка отменена. Выберите действие:",
        reply_markup=teacher_main_menu()
    )

@router.message(VacationRequest.confirm)
async def process_confirm(message: Message, state: FSMContext, bot: Bot):
    if message.text.lower() not in ["да", "yes", "д", "y"]:
        await state.clear()
        await message.answer(
            "❌ Заявка отменена. Выберите действие:",
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
            await message.answer("❌ Пользователь не найден.")
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

        # Notify all secretaries if configured
        for secretary_id in SECRETARY_IDS:
            try:
                await bot.send_message(
                    secretary_id,
                    f"📨 <b>Новая заявка на отпуск!</b>\n\n"
                    f"👤 <b>{user.full_name}</b>\n"
                    f"📞 Телефон: {user.phone}\n"
                    f"📅 Период: {data['start_date'].strftime('%d.%m.%Y')} - "
                    f"{data['end_date'].strftime('%d.%m.%Y')}\n"
                    f"📊 Дней: {data['days_count']}",
                    parse_mode="HTML",
                    reply_markup=vacation_approval(new_vacation.id)
                )
            except Exception as e:
                print(f"Failed to notify secretary: {e}")

    await message.answer(
        "✅ Заявка на отпуск успешно отправлена!\n\n"
        "После подтверждения секретарем вы получите уведомление.",
        reply_markup=teacher_main_menu()
    )
    await state.clear()
