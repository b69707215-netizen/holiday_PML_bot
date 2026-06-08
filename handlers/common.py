from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database import SessionLocal, User, UserRole, BroadcastMessage
from keyboards import role_selection, teacher_main_menu, secretary_main_menu
from states import Registration, PMLBroadcast

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            if user.role == UserRole.TEACHER:
                await message.answer(
                    f"👋 Добро пожаловать, {user.full_name}!\n\n"
                    "Выберите действие:",
                    reply_markup=teacher_main_menu()
                )
            else:
                await message.answer(
                    f"👋 Добро пожаловать, {user.full_name}!\n\n"
                    "Выберите действие:",
                    reply_markup=secretary_main_menu()
                )
        else:
            await message.answer(
                "👋 Добро пожаловать! Для начала работы нужно зарегистрироваться.\n\n"
                "Пожалуйста, введите ваше ФИО:"
            )
            await state.set_state(Registration.full_name)

@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("📱 Введите ваш номер телефона:")
    await state.set_state(Registration.phone)

@router.message(Registration.phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer(
        "👤 Выберите вашу роль:",
        reply_markup=role_selection()
    )
    await state.set_state(Registration.role)

@router.message(Registration.role, F.text.in_(["👨‍🏫 Учитель", "👩‍💼 Секретарь"]))
async def process_role(message: Message, state: FSMContext):
    data = await state.get_data()
    
    role = UserRole.TEACHER if "Учитель" in message.text else UserRole.SECRETARY
    
    async with SessionLocal() as session:
        new_user = User(
            telegram_id=message.from_user.id,
            full_name=data["full_name"],
            phone=data["phone"],
            role=role
        )
        session.add(new_user)
        await session.commit()
    
    await message.answer(
        "✅ Регистрация завершена успешно!\n\n"
        f"ФИО: {data['full_name']}\n"
        f"Телефон: {data['phone']}\n"
        f"Роль: {'Учитель' if role == UserRole.TEACHER else 'Секретарь'}"
    )
    
    if role == UserRole.TEACHER:
        await message.answer(
            "Выберите действие:",
            reply_markup=teacher_main_menu()
        )
    else:
        await message.answer(
            "Выберите действие:",
            reply_markup=secretary_main_menu()
        )

    await state.clear()


@router.message(Command("pml"))
async def cmd_pml(message: Message, state: FSMContext):
    """Subscribe to PML broadcast messages."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                "❌ Сначала необходимо зарегистрироваться.\n"
                "Нажмите /start для регистрации."
            )
            return

        if user.pml_subscribed:
            await message.answer(
                "✅ Вы уже подписаны на рассылку PML!\n\n"
                "Вы будете получать важные сообщения и уведомления."
            )
            return

        # Subscribe user
        user.pml_subscribed = 1
        await session.commit()

        await message.answer(
            "✅ <b>Вы успешно подписались на рассылку PML!</b>\n\n"
            "📢 Теперь вы будете получать:\n"
            "• Важные объявления школы\n"
            "• Напоминания о мероприятиях\n"
            "• Экстренные уведомления\n\n"
            "Чтобы отписаться, используйте команду /pml_off",
            parse_mode="HTML"
        )


@router.message(Command("pml_off"))
async def cmd_pml_off(message: Message):
    """Unsubscribe from PML broadcast messages."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.pml_subscribed:
            await message.answer("❌ Вы не подписаны на рассылку.")
            return

        user.pml_subscribed = 0
        await session.commit()

        await message.answer(
            "✅ Вы отписались от рассылки PML.\n\n"
            "Чтобы снова подписаться, используйте /pml"
        )
