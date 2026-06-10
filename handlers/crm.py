"""
Обработчики для интеграции с CRM системой
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from services.crm_integration import get_crm_integration
from keyboards import secretary_main_menu
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("orders"))
async def show_recent_orders(message: Message):
    """Показать последние приказы из CRM"""
    crm = get_crm_integration()
    if not crm:
        await message.answer(
            "❌ CRM интеграция не доступна",
            reply_markup=secretary_main_menu() if message.from_user.id in [5091636029, 5063427314] else None
        )
        return
    
    await crm.send_recent_orders_summary(message.from_user.id)

@router.message(Command("crm_status"))
async def show_crm_status(message: Message):
    """Показать статус CRM системы"""
    crm = get_crm_integration()
    if not crm:
        await message.answer("❌ CRM интеграция не инициализирована")
        return
    
    try:
        import os
        config = crm.crm_config
        
        status_text = (
            f"📊 <b>Статус CRM интеграции</b>\n\n"
            f"📁 Папка сканов: {config.get('scan_folder', 'Не настроена')}\n"
            f"📁 Обработанные: {config.get('processed_folder', 'Не настроена')}\n"
            f"☁️ Google Drive: {config.get('google_drive_folder', 'Не настроена')}\n"
            f"📢 Уведомления: {'✅ Включены' if config.get('telegram_notifications') else '❌ Выключены'}\n\n"
        )
        
        # Проверяем доступность папок
        scan_folder = config.get('scan_folder')
        if scan_folder and os.path.exists(scan_folder):
            files_count = len(os.listdir(scan_folder))
            status_text += f"📄 Файлов в папке сканов: {files_count}\n"
        else:
            status_text += "❌ Папка сканов недоступна\n"
        
        processed_folder = config.get('processed_folder')
        if processed_folder and os.path.exists(processed_folder):
            processed_files = len([f for f in os.listdir(processed_folder) if f.endswith('.pdf')])
            status_text += f"✅ Обработанных приказов: {processed_files}\n"
        else:
            status_text += "❌ Папка обработанных недоступна\n"
        
        status_text += "\n🔗 Интеграция активна и готова к работе"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing CRM status: {e}")
        await message.answer("❌ Ошибка при получении статуса CRM")

@router.message(Command("test_crm"))
async def test_crm_integration(message: Message):
    """Тестирование интеграции с CRM"""
    # Только для секретарей
    if message.from_user.id not in [5091636029, 5063427314]:
        await message.answer("❌ Команда доступна только секретарям")
        return
    
    crm = get_crm_integration()
    if not crm:
        await message.answer("❌ CRM интеграция не доступна")
        return
    
    await message.answer("🧪 <b>Тестирование CRM интеграции...</b>", parse_mode="HTML")
    
    try:
        # Тест получения последних приказов
        orders = await crm.get_recent_orders(3)
        
        if orders:
            test_message = f"✅ <b>Тест успешен!</b>\n\n📄 Найдено приказов: {len(orders)}\n\n"
            for order in orders[:3]:
                test_message += f"• {order['filename']}\n"
            
            test_message += "\n🔗 CRM интеграция работает корректно"
        else:
            test_message = "⚠️ <b>Тест завершен</b>\n\n❌ Приказы не найдены\n\nВозможные причины:\n• Папка CRM пуста\n• Нет доступа к файлам\n• Некорректная конфигурация"
        
        await message.answer(test_message, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error testing CRM: {e}")
        await message.answer(f"❌ Ошибка при тестировании CRM: {str(e)}")

@router.message(F.text == "📋 CRM Приказы")
async def crm_orders_menu(message: Message):
    """Меню работы с CRM приказами"""
    # Только для секретарей
    if message.from_user.id not in [5091636029, 5063427314]:
        await message.answer("❌ Эта функция доступна только секретарям")
        return
    
    crm = get_crm_integration()
    if not crm:
        await message.answer("❌ CRM интеграция не доступна")
        return
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📄 Последние приказы", "callback_data": "crm_recent_orders"}
            ],
            [
                {"text": "📊 Статус CRM", "callback_data": "crm_status"}
            ],
            [
                {"text": "🧪 Тест интеграции", "callback_data": "crm_test"}
            ],
            [
                {"text": "🔙 Назад", "callback_data": "back_to_main"}
            ]
        ]
    }
    
    await message.answer(
        "📋 <b>Управление CRM приказами</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "crm_recent_orders")
async def callback_crm_recent_orders(callback: CallbackQuery):
    """Показать последние приказы"""
    await show_recent_orders(callback.message)
    await callback.answer()

@router.callback_query(F.data == "crm_status")
async def callback_crm_status(callback: CallbackQuery):
    """Показать статус CRM"""
    await show_crm_status(callback.message)
    await callback.answer()

@router.callback_query(F.data == "crm_test")
async def callback_crm_test(callback: CallbackQuery):
    """Тестирование CRM"""
    await test_crm_integration(callback.message)
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "🔙 Возврат в главное меню",
        reply_markup=secretary_main_menu()
    )
    await callback.answer()
