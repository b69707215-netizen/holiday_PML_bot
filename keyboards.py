from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Main menu for teachers
def teacher_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Мои отпускные дни")
    builder.button(text="📝 Подать заявку на отпуск")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Main menu for secretary
def secretary_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📨 Новые заявки")
    builder.button(text="🔍 Найти учителя по ФИО")
    builder.button(text="📢 Рассылка PML")
    builder.button(text="� CRM Приказы")
    builder.button(text="�👥 Список сотрудников")
    builder.button(text="📊 Мониторинг отпусков")
    builder.button(text="📄 Создать приказ")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Role selection during registration
def role_selection():
    builder = ReplyKeyboardBuilder()
    builder.button(text="👨‍🏫 Учитель")
    builder.button(text="👩‍💼 Секретарь")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

# Vacation request approval/rejection
def vacation_approval(vacation_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Одобрить",
        callback_data=f"approve_vacation:{vacation_id}"
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"reject_vacation:{vacation_id}"
    )
    builder.adjust(2)
    return builder.as_markup()

# Order type selection
def order_type_selection():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏖️ Отпуск")
    builder.button(text="🌸 Весняні канікули")
    builder.button(text="💪 Молодь за здоров'я")
    builder.button(text="🛡️ 16 днів проти насильства")
    builder.button(text="🏕️ Джура")
    builder.button(text="❌ Отмена")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Cancel button
def cancel_button():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True)

# Back button
def back_button():
    builder = ReplyKeyboardBuilder()
    builder.button(text="⬅️ Назад")
    return builder.as_markup(resize_keyboard=True)

# PML broadcast confirmation
def pml_broadcast_confirm():
    builder = ReplyKeyboardBuilder()
    builder.button(text="✅ Отправить рассылку")
    builder.button(text="❌ Отмена")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)
