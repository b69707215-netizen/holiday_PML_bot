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
                    f"👋 Вітаємо, {user.full_name}!\n\n"
                    "Оберіть дію:",
                    reply_markup=teacher_main_menu()
                )
            else:
                await message.answer(
                    f"👋 Вітаємо, {user.full_name}!\n\n"
                    "Оберіть дію:",
                    reply_markup=secretary_main_menu()
                )
        else:
            await message.answer(
                "👋 Вітаємо! Для початку роботи потрібно зареєструватися.\n\n"
                "Будь ласка, введіть ваше ПІБ (Прізвище Ім'я По батькові):"
            )
            await state.set_state(Registration.full_name)

@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("📱 Введіть ваш номер телефону:")
    await state.set_state(Registration.phone)

@router.message(Registration.phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer(
        "👤 Оберіть вашу роль:",
        reply_markup=role_selection()
    )
    await state.set_state(Registration.role)

@router.message(Registration.role, F.text.in_(["👨‍🏫 Вчитель", "👩‍💼 Секретар"]))
async def process_role(message: Message, state: FSMContext):
    data = await state.get_data()
    
    role = UserRole.TEACHER if "Вчитель" in message.text else UserRole.SECRETARY
    
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
        "✅ Реєстрацію успішно завершено!\n\n"
        f"ПІБ: {data['full_name']}\n"
        f"Телефон: {data['phone']}\n"
        f"Роль: {'Вчитель' if role == UserRole.TEACHER else 'Секретар'}"
    )
    
    if role == UserRole.TEACHER:
        await message.answer(
            "Оберіть дію:",
            reply_markup=teacher_main_menu()
        )
    else:
        await message.answer(
            "Оберіть дію:",
            reply_markup=secretary_main_menu()
        )

    await state.clear()


@router.message(Command("pml"))
async def cmd_pml(message: Message, state: FSMContext):
    """Підписатися на розсилку PML."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                "❌ Спочатку потрібно зареєструватися.\n"
                "Натисніть /start для реєстрації."
            )
            return

        if user.pml_subscribed:
            await message.answer(
                "✅ Ви вже підписані на розсилку PML!\n\n"
                "Ви будете отримувати важливі повідомлення та сповіщення."
            )
            return

        user.pml_subscribed = 1
        await session.commit()

        await message.answer(
            "✅ <b>Ви успішно підписалися на розсилку PML!</b>\n\n"
            "📢 Тепер ви будете отримувати:\n"
            "• Важливі оголошення школи\n"
            "• Нагадування про заходи\n"
            "• Термінові сповіщення\n\n"
            "Щоб відписатися — скористайтеся командою /pml_off",
            parse_mode="HTML"
        )


@router.message(Command("pml_off"))
async def cmd_pml_off(message: Message):
    """Відписатися від розсилки PML."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.pml_subscribed:
            await message.answer("❌ Ви не підписані на розсилку.")
            return

        user.pml_subscribed = 0
        await session.commit()

        await message.answer(
            "✅ Ви відписалися від розсилки PML.\n\n"
            "Щоб знову підписатися — скористайтеся /pml"
        )
