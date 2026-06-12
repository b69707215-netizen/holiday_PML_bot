"""
Хендлери для директора:
- Призначення заступника директора
- Перегляд списку заступників
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database import SessionLocal, User, UserRole
from keyboards import director_main_menu, confirm_appoint_keyboard, cancel_button
from states import AppointVice
from config import DIRECTOR_ID

router = Router()

def is_director(user_id: int) -> bool:
    return user_id == DIRECTOR_ID

# ───────────────────────────────────────────────
# Призначення заступника
# ───────────────────────────────────────────────

@router.message(F.text == "👔 Призначити заступника")
async def appoint_vice_start(message: Message, state: FSMContext):
    if not is_director(message.from_user.id):
        await message.answer("❌ Тільки директор може призначати заступників.")
        return

    await message.answer(
        "🔍 Введіть ПІБ (або частину) співробітника, якого хочете призначити заступником:",
        reply_markup=cancel_button()
    )
    await state.set_state(AppointVice.search_name)

@router.message(AppointVice.search_name, F.text == "❌ Скасувати")
async def appoint_vice_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Скасовано.", reply_markup=director_main_menu())

@router.message(AppointVice.search_name)
async def appoint_vice_search(message: Message, state: FSMContext):
    query = message.text.strip()
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.full_name.ilike(f"%{query}%"))
        )
        users = result.scalars().all()

    if not users:
        await message.answer("❌ Нікого не знайдено. Спробуйте ще раз:")
        return

    if len(users) > 10:
        await message.answer(f"Знайдено {len(users)} осіб — уточніть ПІБ:")
        return

    # Показуємо список
    lines = []
    for u in users:
        role_label = {
            UserRole.DIRECTOR: "Директор",
            UserRole.VICE_PRINCIPAL: "Заступник",
            UserRole.SECRETARY: "Секретар",
            UserRole.TEACHER: "Вчитель",
        }.get(u.role, u.role.value)
        lines.append(f"• {u.full_name} [{role_label}] — ID: {u.telegram_id}")

    await message.answer(
        "Знайдені співробітники:\n" + "\n".join(lines) +
        "\n\nВведіть точне ПІБ для призначення:"
    )
    await state.update_data(candidates=[u.telegram_id for u in users])

    # Якщо тільки один — одразу пропонуємо підтвердження
    if len(users) == 1:
        u = users[0]
        await state.update_data(target_id=u.telegram_id, target_name=u.full_name)
        await message.answer(
            f"Призначити <b>{u.full_name}</b> заступником директора?",
            reply_markup=confirm_appoint_keyboard(u.telegram_id),
            parse_mode="HTML"
        )
        await state.set_state(AppointVice.confirm)

@router.message(AppointVice.search_name)
async def appoint_vice_exact(message: Message, state: FSMContext):
    """Точне ПІБ після показу списку"""
    query = message.text.strip()
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.full_name == query)
        )
        user = result.scalar_one_or_none()

    if not user:
        await message.answer("❌ Не знайдено точного збігу. Введіть ПІБ як у списку вище:")
        return

    await state.update_data(target_id=user.telegram_id, target_name=user.full_name)
    await message.answer(
        f"Призначити <b>{user.full_name}</b> заступником директора?",
        reply_markup=confirm_appoint_keyboard(user.telegram_id),
        parse_mode="HTML"
    )
    await state.set_state(AppointVice.confirm)

@router.callback_query(F.data.startswith("appoint_vice:"))
async def confirm_appoint(callback: CallbackQuery, state: FSMContext):
    if not is_director(callback.from_user.id):
        await callback.answer("❌ Тільки директор.", show_alert=True)
        return

    target_telegram_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_telegram_id)
        )
        target_user = result.scalar_one_or_none()

        director_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        director = director_result.scalar_one_or_none()

        if not target_user:
            await callback.answer("❌ Користувача не знайдено.", show_alert=True)
            return

        target_user.role = UserRole.VICE_PRINCIPAL
        if director:
            target_user.appointed_by = director.id
        await session.commit()

    await callback.message.edit_text(
        f"✅ <b>{target_user.full_name}</b> призначено заступником директора!",
        parse_mode="HTML"
    )
    await callback.answer()
    await state.clear()

    # Повідомити самого заступника
    try:
        await callback.bot.send_message(
            target_telegram_id,
            "🎉 Вас призначено <b>заступником директора</b> у системі Holiday PML Bot!\n"
            "Натисніть /start щоб оновити меню.",
            parse_mode="HTML"
        )
    except Exception:
        pass

@router.callback_query(F.data == "appoint_cancel")
async def cancel_appoint(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Скасовано.")
    await callback.answer()
    await state.clear()

# ───────────────────────────────────────────────
# Перегляд заступників
# ───────────────────────────────────────────────

@router.message(F.text == "🗂️ Заступники")
async def list_vice_principals(message: Message):
    if not is_director(message.from_user.id):
        await message.answer("❌ Тільки для директора.")
        return

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.VICE_PRINCIPAL)
        )
        vices = result.scalars().all()

    if not vices:
        await message.answer("Заступників ще не призначено.")
        return

    lines = [f"• {v.full_name} (tg: {v.telegram_id})" for v in vices]
    await message.answer("👔 Заступники директора:\n" + "\n".join(lines))
