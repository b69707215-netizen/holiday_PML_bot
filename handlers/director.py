"""
Хендлери для директора:
- Меню директора (3 кнопки)
- Призначення персоналу по номеру телефону (секретар / заступник)
- Вкладка наказів — схвалені відпустки + генерація docx
- Вкладка відпусток
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import SessionLocal, User, UserRole, Vacation, VacationStatus
from keyboards import (
    director_main_menu, cancel_button,
    confirm_appoint_keyboard, appoint_role_keyboard,
)
from states import AppointVice
from config import DIRECTOR_ID

router = Router()

def is_director(user_id: int) -> bool:
    return user_id == DIRECTOR_ID

# ─────────────────────────────────────────────────────────
# 1. ПРИЗНАЧИТИ ПЕРСОНАЛ — по номеру телефону
# ─────────────────────────────────────────────────────────

@router.message(F.text == "👤 Призначити персонал")
async def appoint_staff_start(message: Message, state: FSMContext):
    if not is_director(message.from_user.id):
        await message.answer("❌ Тільки для директора.")
        return

    await message.answer(
        "📱 Введіть номер телефону співробітника (у форматі +380...):\n\n"
        "Система знайде людину і запитає яку роль призначити.",
        reply_markup=cancel_button()
    )
    await state.set_state(AppointVice.search_name)
    await state.update_data(appoint_mode="phone")

@router.message(AppointVice.search_name, F.text == "❌ Скасувати")
async def appoint_cancel_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Скасовано.", reply_markup=director_main_menu())

@router.message(AppointVice.search_name)
async def appoint_search_by_phone(message: Message, state: FSMContext):
    query = message.text.strip()

    # Нормалізуємо телефон
    phone = re.sub(r"[^\d+]", "", query)
    if not phone.startswith("+"):
        phone = "+" + phone

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.phone == phone)
        )
        user = result.scalar_one_or_none()

    if not user:
        # Пробуємо по ПІБ як fallback
        async with SessionLocal() as session:
            result = await session.execute(
                select(User).where(User.full_name.ilike(f"%{query}%"))
            )
            users = result.scalars().all()

        if not users:
            await message.answer(
                "❌ Співробітника не знайдено.\n"
                "Перевірте номер або введіть ПІБ:"
            )
            return

        if len(users) == 1:
            user = users[0]
        else:
            lines = [f"• {u.full_name} — {u.phone}" for u in users[:10]]
            await message.answer(
                "Знайдено кілька:\n" + "\n".join(lines) +
                "\n\nУточніть номер телефону:"
            )
            return

    # Знайдено — показуємо і питаємо роль
    role_label = {
        UserRole.DIRECTOR: "Директор",
        UserRole.VICE_PRINCIPAL: "Заступник директора",
        UserRole.SECRETARY: "Секретар",
        UserRole.TEACHER: "Вчитель",
    }.get(user.role, user.role.value)

    await state.update_data(target_id=user.telegram_id, target_name=user.full_name)
    await message.answer(
        f"👤 <b>{user.full_name}</b>\n"
        f"📱 {user.phone}\n"
        f"Поточна роль: {role_label}\n\n"
        "Оберіть нову роль:",
        reply_markup=appoint_role_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AppointVice.confirm)

@router.callback_query(F.data.startswith("appoint_role:"))
async def appoint_choose_role(callback: CallbackQuery, state: FSMContext):
    if not is_director(callback.from_user.id):
        await callback.answer("❌ Тільки директор.", show_alert=True)
        return

    role_key = callback.data.split(":")[1]
    data = await state.get_data()
    target_id = data.get("target_id")
    target_name = data.get("target_name")

    if not target_id:
        await callback.answer("Помилка — почніть знову.", show_alert=True)
        await state.clear()
        return

    role_map = {
        "vice": UserRole.VICE_PRINCIPAL,
        "secretary": UserRole.SECRETARY,
    }
    new_role = role_map.get(role_key)
    if not new_role:
        await callback.answer("Невідома роль.", show_alert=True)
        return

    role_labels = {
        UserRole.VICE_PRINCIPAL: "Заступник директора",
        UserRole.SECRETARY: "Секретар",
    }

    await callback.message.edit_text(
        f"Призначити <b>{target_name}</b> як <b>{role_labels[new_role]}</b>?",
        reply_markup=confirm_appoint_keyboard(target_id, role_key),
        parse_mode="HTML"
    )
    await state.update_data(new_role=role_key)
    await callback.answer()

@router.callback_query(F.data.startswith("appoint_vice:") | F.data.startswith("appoint_secretary:"))
async def confirm_appoint(callback: CallbackQuery, state: FSMContext):
    if not is_director(callback.from_user.id):
        await callback.answer("❌ Тільки директор.", show_alert=True)
        return

    parts = callback.data.split(":")
    role_key = parts[0].replace("appoint_", "")
    target_telegram_id = int(parts[1])

    role_map = {
        "vice": UserRole.VICE_PRINCIPAL,
        "secretary": UserRole.SECRETARY,
    }
    new_role = role_map.get(role_key, UserRole.TEACHER)
    role_labels = {
        UserRole.VICE_PRINCIPAL: "Заступник директора 👔",
        UserRole.SECRETARY: "Секретар 👩‍💼",
    }

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

        target_user.role = new_role
        if director:
            target_user.appointed_by = director.id
        await session.commit()
        name = target_user.full_name

    await callback.message.edit_text(
        f"✅ <b>{name}</b> призначено як <b>{role_labels.get(new_role, new_role.value)}</b>!",
        parse_mode="HTML"
    )
    await callback.answer()
    await state.clear()

    # Повідомити призначеного
    try:
        await callback.bot.send_message(
            target_telegram_id,
            f"🎉 Вас призначено <b>{role_labels.get(new_role, '')}</b> у системі!\n"
            "Натисніть /start щоб оновити меню.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.message.answer("Меню:", reply_markup=director_main_menu())

@router.callback_query(F.data == "appoint_cancel")
async def cancel_appoint(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Скасовано.")
    await callback.answer()
    await state.clear()
    await callback.message.answer("Меню:", reply_markup=director_main_menu())

# ─────────────────────────────────────────────────────────
# 2. ВІДПУСТКИ — директор переглядає всі схвалені
# ─────────────────────────────────────────────────────────

@router.message(F.text == "🏖 Відпустки")
async def director_vacations(message: Message):
    if not is_director(message.from_user.id):
        await message.answer("❌ Тільки для директора.")
        return

    async with SessionLocal() as session:
        result = await session.execute(
            select(Vacation)
            .options(selectinload(Vacation.user))
            .where(Vacation.status == VacationStatus.APPROVED)
            .order_by(Vacation.start_date.desc())
        )
        vacations = result.scalars().all()

    if not vacations:
        await message.answer("📭 Схвалених відпусток немає.")
        return

    lines = []
    for i, v in enumerate(vacations, 1):
        lines.append(
            f"{i}. <b>{v.user.full_name}</b>\n"
            f"   📅 {v.start_date} – {v.end_date} ({v.days_count} дн.)"
        )

    await message.answer(
        "🏖 <b>Схвалені відпустки:</b>\n\n" + "\n\n".join(lines),
        parse_mode="HTML"
    )


