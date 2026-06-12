"""
Обробники для інтеграції з CRM системою
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from services.crm_integration import get_crm_integration
from keyboards import secretary_main_menu
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("orders"))
async def show_recent_orders(message: Message):
    """Показати останні накази з CRM"""
    crm = get_crm_integration()
    if not crm:
        await message.answer(
            "❌ CRM інтеграція недоступна",
            reply_markup=secretary_main_menu() if message.from_user.id in [5091636029, 5063427314] else None
        )
        return
    
    await crm.send_recent_orders_summary(message.from_user.id)

@router.message(Command("crm_status"))
async def show_crm_status(message: Message):
    """Показати статус CRM системи"""
    crm = get_crm_integration()
    if not crm:
        await message.answer("❌ CRM інтеграцію не ініціалізовано")
        return
    
    try:
        import os
        config = crm.crm_config
        
        status_text = (
            f"📊 <b>Статус CRM інтеграції</b>\n\n"
            f"📁 Папка сканів: {config.get('scan_folder', 'Не налаштована')}\n"
            f"📁 Оброблені: {config.get('processed_folder', 'Не налаштована')}\n"
            f"☁️ Google Drive: {config.get('google_drive_folder', 'Не налаштована')}\n"
            f"📢 Сповіщення: {'✅ Увімкнені' if config.get('telegram_notifications') else '❌ Вимкнені'}\n\n"
        )
        
        scan_folder = config.get('scan_folder')
        if scan_folder and os.path.exists(scan_folder):
            files_count = len(os.listdir(scan_folder))
            status_text += f"📄 Файлів у папці сканів: {files_count}\n"
        else:
            status_text += "❌ Папка сканів недоступна\n"
        
        processed_folder = config.get('processed_folder')
        if processed_folder and os.path.exists(processed_folder):
            processed_files = len([f for f in os.listdir(processed_folder) if f.endswith('.pdf')])
            status_text += f"✅ Оброблених наказів: {processed_files}\n"
        else:
            status_text += "❌ Папка оброблених недоступна\n"
        
        status_text += "\n🔗 Інтеграція активна та готова до роботи"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing CRM status: {e}")
        await message.answer("❌ Помилка при отриманні статусу CRM")

@router.message(Command("test_crm"))
async def test_crm_integration(message: Message):
    """Тестування інтеграції з CRM"""
    if message.from_user.id not in [5091636029, 5063427314]:
        await message.answer("❌ Команда доступна лише секретарям")
        return
    
    crm = get_crm_integration()
    if not crm:
        await message.answer("❌ CRM інтеграція недоступна")
        return
    
    await message.answer("🧪 <b>Тестування CRM інтеграції...</b>", parse_mode="HTML")
    
    try:
        orders = await crm.get_recent_orders(3)
        
        if orders:
            test_message = f"✅ <b>Тест успішний!</b>\n\n📄 Знайдено наказів: {len(orders)}\n\n"
            for order in orders[:3]:
                test_message += f"• {order['filename']}\n"
            test_message += "\n🔗 CRM інтеграція працює коректно"
        else:
            test_message = (
                "⚠️ <b>Тест завершено</b>\n\n❌ Накази не знайдено\n\n"
                "Можливі причини:\n• Папка CRM порожня\n• Немає доступу до файлів\n• Некоректна конфігурація"
            )
        
        await message.answer(test_message, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error testing CRM: {e}")
        await message.answer(f"❌ Помилка при тестуванні CRM: {str(e)}")

@router.message(F.text == "📋 CRM Накази")
async def crm_orders_menu(message: Message):
    """Меню роботи з CRM наказами"""
    if message.from_user.id not in [5091636029, 5063427314]:
        await message.answer("❌ Ця функція доступна лише секретарям")
        return
    
    crm = get_crm_integration()
    if not crm:
        await message.answer("❌ CRM інтеграція недоступна")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Останні накази", callback_data="crm_recent_orders")],
            [InlineKeyboardButton(text="📊 Статус CRM", callback_data="crm_status")],
            [InlineKeyboardButton(text="🧪 Тест інтеграції", callback_data="crm_test")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ]
    )
    
    await message.answer(
        "📋 <b>Управління CRM наказами</b>\n\n"
        "Оберіть дію:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "crm_recent_orders")
async def callback_crm_recent_orders(callback: CallbackQuery):
    await show_recent_orders(callback.message)
    await callback.answer()

@router.callback_query(F.data == "crm_status")
async def callback_crm_status(callback: CallbackQuery):
    await show_crm_status(callback.message)
    await callback.answer()

@router.callback_query(F.data == "crm_test")
async def callback_crm_test(callback: CallbackQuery):
    await test_crm_integration(callback.message)
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "🔙 Повернення до головного меню",
        reply_markup=secretary_main_menu()
    )
    await callback.answer()
