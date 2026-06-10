"""
Обработчики загрузки документов в CRM систему
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, Document
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from services.telegram_to_crm import get_telegram_to_crm
from keyboards import secretary_main_menu
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.document)
async def handle_document_upload(message: Message):
    """Обработка загрузки документа"""
    crm = get_telegram_to_crm()
    if not crm:
        await message.answer("❌ CRM система недоступна")
        return
    
    # Проверяем, что это PDF файл (приказ)
    if message.document.file_name and message.document.file_name.lower().endswith('.pdf'):
        await message.answer("📄 <b>Получен приказ для CRM</b>\n\n⏳ Сохраняю в систему...", parse_mode="HTML")
        
        success = await crm.save_document_to_crm(message, message.document)
        
        if success:
            await message.answer(
                "✅ <b>Приказ успешно сохранен в CRM!</b>\n\n"
                "📁 Документ добавлен в систему обработки\n"
                "🔄 CRM автоматически обработает документ",
                parse_mode="HTML",
                reply_markup=secretary_main_menu() if message.from_user.id in [5091636029, 5063427314] else None
            )
        else:
            await message.answer("❌ Ошибка при сохранении документа в CRM")
    else:
        await message.answer(
            "📄 <b>Получен документ</b>\n\n"
            "⏳ Сохраняю в систему...",
            parse_mode="HTML"
        )
        
        success = await crm.save_document_to_crm(message, message.document)
        
        if success:
            await message.answer(
                "✅ <b>Документ успешно сохранен в CRM!</b>\n\n"
                "📁 Документ добавлен в систему обработки",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка при сохранении документа в CRM")

@router.message(F.photo)
async def handle_photo_upload(message: Message):
    """Обработка загрузки фото"""
    crm = get_telegram_to_crm()
    if not crm:
        await message.answer("❌ CRM система недоступна")
        return
    
    await message.answer("📷 <b>Получено фото для CRM</b>\n\n⏳ Сохраняю в систему...", parse_mode="HTML")
    
    success = await crm.save_document_to_crm(message)
    
    if success:
        await message.answer(
            "✅ <b>Фото успешно сохранено в CRM!</b>\n\n"
            "📁 Изображение добавлено в систему обработки",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка при сохранении фото в CRM")

@router.message(Command("upload_to_crm"))
async def upload_to_crm_instruction(message: Message):
    """Инструкция по загрузке документов в CRM"""
    instruction_text = (
        "📋 <b>Загрузка документов в CRM систему</b>\n\n"
        "📄 <b>Как загрузить приказ:</b>\n"
        "1. Отправьте PDF файл с приказом в чат\n"
        "2. Добавьте подпись с описанием (необязательно)\n"
        "3. Документ автоматически сохранится в CRM\n\n"
        "📷 <b>Как загрузить фото:</b>\n"
        "1. Отправьте фото документа\n"
        "2. Фото автоматически обработается CRM\n\n"
        "📁 <b>Куда сохраняются документы:</b>\n"
        "• Приказы: E:/СРМ/Scans/Orders/\n"
        "• Другие документы: E:/СРМ/Scans/Inbox/\n\n"
        "🔄 CRM автоматически обработает все документы"
    )
    
    await message.answer(instruction_text, parse_mode="HTML")

@router.message(Command("crm_stats"))
async def show_crm_statistics(message: Message):
    """Показать статистику загрузок в CRM"""
    crm = get_telegram_to_crm()
    if not crm:
        await message.answer("❌ CRM система недоступна")
        return
    
    await message.answer("📊 <b>Статистика загрузок в CRM</b>\n\n⏳ Загружаю данные...", parse_mode="HTML")
    
    stats = await crm.get_upload_statistics()
    
    if "error" in stats:
        await message.answer(f"❌ Ошибка получения статистики: {stats['error']}")
        return
    
    stats_text = (
        f"📊 <b>Статистика загрузок в CRM</b>\n\n"
        f"📁 Всего файлов: {stats['total_files']}\n\n"
        f"📋 <b>По типам:</b>\n"
    )
    
    for doc_type, count in stats.get("by_type", {}).items():
        type_names = {
            "order": "📄 Приказы",
            "application": "📝 Заявления", 
            "certificate": "📋 Справки",
            "termination": "❌ Увольнения",
            "contract": "📋 Договоры",
            "other": "📄 Другое"
        }
        stats_text += f"{type_names.get(doc_type, '📄 ' + doc_type)}: {count}\n"
    
    if stats.get("recent_uploads"):
        stats_text += f"\n🕒 <b>Последние загрузки:</b>\n"
        for upload in stats["recent_uploads"][-3:]:  # Последние 3
            timestamp = upload.get("timestamp", "")[:19].replace("T", " ")
            user_name = upload.get("user_name", "Unknown")
            doc_type = upload.get("doc_type", "other")
            stats_text += f"• {timestamp} - {user_name} ({doc_type})\n"
    
    await message.answer(stats_text, parse_mode="HTML")

@router.message(F.text == "📤 Загрузить в CRM")
async def upload_to_crm_menu(message: Message):
    """Меню загрузки в CRM"""
    # Только для секретарей
    if message.from_user.id not in [5091636029, 5063427314]:
        await message.answer("❌ Эта функция доступна только секретарям")
        return
    
    instruction_text = (
        "📤 <b>Загрузка документов в CRM</b>\n\n"
        "👇 <b>Просто отправьте документ в этот чат:</b>\n\n"
        "📄 PDF файл - для приказов\n"
        "📷 Фото - для других документов\n\n"
        "💡 <b>Совет:</b> Добавьте подпись к документу для лучшей классификации"
    )
    
    await message.answer(instruction_text, parse_mode="HTML")
