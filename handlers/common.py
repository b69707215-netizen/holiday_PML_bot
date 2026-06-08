from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database import SessionLocal, User, UserRole
from keyboards import role_selection, teacher_main_menu, secretary_main_menu
from states import Registration

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
