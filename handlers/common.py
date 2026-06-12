from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database import SessionLocal, User, UserRole, BroadcastMessage
from keyboards import (
    role_selection, teacher_main_menu, secretary_main_menu,
    director_main_menu, vice_principal_main_menu, request_contact_keyboard
)
from states import Registration, PMLBroadcast
from config import DIRECTOR_ID

router = Router()

def get_menu_by_role(role: UserRole):
    if role == UserRole.DIRECTOR:
        return director_main_menu()
    elif role == UserRole.VICE_PRINCIPAL:
        return vice_principal_main_menu()
    elif role == UserRole.SECRETARY:
        return secretary_main_menu()
    else:
        return teacher_main_menu()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            role_labels = {
                UserRole.DIRECTOR: "Директор",
                UserRole.VICE_PRINCIPAL: "Заступник директора",
                UserRole.SECRETARY: "Секретар",
                UserRole.TEACHER: "Вчитель",
            }
            await message.answer(
                f"👋 Вітаємо, {user.full_name}!\n\n"
                "Оберіть дію:",
                reply_markup=get_menu_by_role(user.role)
            )
        else:
            await message.answer(
                "👋 Вітаємо! Для початку роботи потрібно зареєструватися.\n\n"
                "Будь ласка, введіть ваше ПІБ (Прізвище Ім'я По батькові):"
            )
            await state.set_state(Registration.full_name)

@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext):
    # Якщо замість тексту надіслали контакт — ігноруємо (не той стан)
    if message.contact:
        await message.answer("❗ Спочатку введіть ваше ПІБ текстом.")
        return

    full_name = message.text.strip() if message.text else ""
    if len(full_name) < 3:
        await message.answer("❗ Введіть повне ПІБ (мінімум 3 символи):")
        return
    await state.update_data(full_name=full_name)

    if message.from_user.id == DIRECTOR_ID:
        await state.update_data(is_director=True)

    await message.answer(
        "📱 Натисніть кнопку нижче, щоб поділитися своїм номером телефону:",
        reply_markup=request_contact_keyboard()
    )
    await state.set_state(Registration.phone)

@router.message(Registration.phone, F.contact)
async def process_contact(message: Message, state: FSMContext):
    """Обробка контакту під час реєстрації"""
    data = await state.get_data()
    full_name = data.get("full_name")

    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    is_director = data.get("is_director", False) or message.from_user.id == DIRECTOR_ID

    if is_director:
        await _register_user(message, state, full_name, phone, UserRole.DIRECTOR)
    else:
        await state.update_data(phone=phone)
        await message.answer(
            "👤 Оберіть вашу роль:",
            reply_markup=role_selection()
        )
        await state.set_state(Registration.role)

@router.message(Registration.phone)
async def process_phone_wrong(message: Message, state: FSMContext):
    """Якщо надіслали текст замість контакту"""
    await message.answer(
        "📱 Будь ласка, скористайтеся кнопкою нижче для поділитися номером телефону:",
        reply_markup=request_contact_keyboard()
    )

@router.message(Registration.role, F.text.in_(["👨‍🏫 Вчитель", "👩‍💼 Секретар"]))
async def process_role(message: Message, state: FSMContext):
    data = await state.get_data()
    role = UserRole.TEACHER if "Вчитель" in message.text else UserRole.SECRETARY
    await _register_user(message, state, data["full_name"], data["phone"], role)

async def _register_user(message: Message, state: FSMContext, full_name: str, phone: str, role: UserRole):
    async with SessionLocal() as session:
        # Перевірка дублікату
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            await message.answer(
                "✅ Ви вже зареєстровані!",
                reply_markup=get_menu_by_role(existing.role)
            )
            await state.clear()
            return

        new_user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,  # може бути None
            full_name=full_name,
            phone=phone,
            role=role
        )
        session.add(new_user)
        await session.commit()

    role_labels = {
        UserRole.DIRECTOR: "Директор 👔",
        UserRole.VICE_PRINCIPAL: "Заступник директора",
        UserRole.SECRETARY: "Секретар 👩‍💼",
        UserRole.TEACHER: "Вчитель 👨‍🏫",
    }

    await message.answer(
        f"✅ Реєстрацію успішно завершено!\n\n"
        f"ПІБ: {full_name}\n"
        f"Телефон: {phone}\n"
        f"Роль: {role_labels.get(role, role.value)}"
    )
    await message.answer("Оберіть дію:", reply_markup=get_menu_by_role(role))
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
