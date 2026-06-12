from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Головне меню для вчителів
def teacher_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Мої відпускні дні")
    builder.button(text="📝 Подати заявку на відпустку")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Головне меню для секретаря
def secretary_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📨 Нові заявки")
    builder.button(text="🔍 Знайти вчителя за ПІБ")
    builder.button(text="📢 Розсилка PML")
    builder.button(text="📋 CRM Накази")
    builder.button(text="📤 Завантажити в CRM")
    builder.button(text="👥 Список співробітників")
    builder.button(text="📊 Моніторинг відпусток")
    builder.button(text="📄 Створити наказ")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Головне меню для заступника директора
def vice_principal_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📨 Нові заявки")
    builder.button(text="🔍 Знайти вчителя за ПІБ")
    builder.button(text="📢 Розсилка PML")
    builder.button(text="📋 CRM Накази")
    builder.button(text="📤 Завантажити в CRM")
    builder.button(text="👥 Список співробітників")
    builder.button(text="📊 Моніторинг відпусток")
    builder.button(text="📄 Створити наказ")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Головне меню для директора — тільки 3 кнопки
def director_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Призначити персонал")
    builder.button(text="📋 Створити накази")
    builder.button(text="🏖 Відпустки")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

# Кнопка "Поділитися контактом" при реєстрації
def request_contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поділитися контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Вибір ролі під час реєстрації (тільки вчитель/секретар — директор авто)
def role_selection():
    builder = ReplyKeyboardBuilder()
    builder.button(text="👨‍🏫 Вчитель")
    builder.button(text="👩‍💼 Секретар")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

# Схвалення / відхилення заявки на відпустку
def vacation_approval(vacation_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Схвалити",
        callback_data=f"approve_vacation:{vacation_id}"
    )
    builder.button(
        text="❌ Відхилити",
        callback_data=f"reject_vacation:{vacation_id}"
    )
    builder.adjust(2)
    return builder.as_markup()

# Вибір типу наказу
def order_type_selection():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏖️ Відпустка")
    builder.button(text="🌸 Весняні канікули")
    builder.button(text="💪 Молодь за здоров'я")
    builder.button(text="🛡️ 16 днів проти насильства")
    builder.button(text="🏕️ Джура")
    builder.button(text="❌ Скасувати")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Кнопка скасування
def cancel_button():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Скасувати")
    return builder.as_markup(resize_keyboard=True)

# Кнопка назад
def back_button():
    builder = ReplyKeyboardBuilder()
    builder.button(text="⬅️ Назад")
    return builder.as_markup(resize_keyboard=True)

# Підтвердження розсилки PML
def pml_broadcast_confirm():
    builder = ReplyKeyboardBuilder()
    builder.button(text="✅ Надіслати розсилку")
    builder.button(text="❌ Скасувати")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Inline: підтвердження призначення заступника / секретаря
def confirm_appoint_keyboard(user_id: int, role: str = "vice"):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Підтвердити", callback_data=f"appoint_{role}:{user_id}")
    builder.button(text="❌ Скасувати", callback_data="appoint_cancel")
    builder.adjust(2)
    return builder.as_markup()

# Inline: вибір ролі для призначення
def appoint_role_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👔 Заступник директора", callback_data="appoint_role:vice")
    builder.button(text="👩‍💼 Секретар", callback_data="appoint_role:secretary")
    builder.adjust(1)
    return builder.as_markup()

# Inline: список схвалених відпусток для генерації наказу
def approved_vacations_keyboard(vacations: list):
    builder = InlineKeyboardBuilder()
    for v in vacations:
        label = f"{v.user.full_name} | {v.start_date} – {v.end_date} ({v.days_count} дн.)"
        builder.button(text=label, callback_data=f"gen_order:{v.id}")
    builder.adjust(1)
    return builder.as_markup()
