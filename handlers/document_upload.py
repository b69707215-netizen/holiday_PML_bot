"""
Обробники завантаження документів у CRM систему
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
    """Обробка завантаження документа"""
    crm = get_telegram_to_crm()
    if not crm:
        await message.answer("❌ CRM система недоступна")
        return
    
    if message.document.file_name and message.document.file_name.lower().endswith('.pdf'):
        await message.answer("📄 <b>Отримано наказ для CRM</b>\n\n⏳ Зберігаю в систему...", parse_mode="HTML")
        
        success = await crm.save_document_to_crm(message, message.document)
        
        if success:
            await message.answer(
                "✅ <b>Наказ успішно збережено в CRM!</b>\n\n"
                "📁 Документ додано до системи обробки\n"
                "🔄 CRM автоматично обробить документ",
                parse_mode="HTML",
                reply_markup=secretary_main_menu() if message.from_user.id in [5091636029, 5063427314] else None
            )
        else:
            await message.answer("❌ Помилка при збереженні документа в CRM")
    else:
        await message.answer(
            "📄 <b>Отримано документ</b>\n\n"
            "⏳ Зберігаю в систему...",
            parse_mode="HTML"
        )
        
        success = await crm.save_document_to_crm(message, message.document)
        
        if success:
            await message.answer(
                "✅ <b>Документ успішно збережено в CRM!</b>\n\n"
                "📁 Документ додано до системи обробки",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Помилка при збереженні документа в CRM")

@router.message(F.photo)
async def handle_photo_upload(message: Message):
    """Обробка завантаження фото"""
    crm = get_telegram_to_crm()
    if not crm:
        await message.answer("❌ CRM система недоступна")
        return
    
    await message.answer("📷 <b>Отримано фото для CRM</b>\n\n⏳ Зберігаю в систему...", parse_mode="HTML")
    
    success = await crm.save_document_to_crm(message)
    
    if success:
        await message.answer(
            "✅ <b>Фото успішно збережено в CRM!</b>\n\n"
            "📁 Зображення додано до системи обробки",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Помилка при збереженні фото в CRM")

@router.message(Command("upload_to_crm"))
async def upload_to_crm_instruction(message: Message):
    """Інструкція з завантаження документів у CRM"""
    instruction_text = (
        "📋 <b>Завантаження документів у CRM систему</b>\n\n"
        "📄 <b>Як завантажити наказ:</b>\n"
        "1. Надішліть PDF файл з наказом у чат\n"
        "2. Додайте підпис з описом (необов'язково)\n"
        "3. Документ автоматично збережеться в CRM\n\n"
        "📷 <b>Як завантажити фото:</b>\n"
        "1. Надішліть фото документа\n"
        "2. Фото автоматично обробиться CRM\n\n"
        "📁 <b>Куди зберігаються документи:</b>\n"
        "• Накази: E:/СРМ/Scans/Orders/\n"
        "• Інші документи: E:/СРМ/Scans/Inbox/\n\n"
        "🔄 CRM автоматично обробить усі документи"
    )
    
    await message.answer(instruction_text, parse_mode="HTML")

@router.message(Command("crm_stats"))
async def show_crm_statistics(message: Message):
    """Показати статистику завантажень у CRM"""
    crm = get_telegram_to_crm()
    if not crm:
        await message.answer("❌ CRM система недоступна")
        return
    
    await message.answer("📊 <b>Статистика завантажень у CRM</b>\n\n⏳ Завантажую дані...", parse_mode="HTML")
    
    stats = await crm.get_upload_statistics()
    
    if "error" in stats:
        await message.answer(f"❌ Помилка отримання статистики: {stats['error']}")
        return
    
    stats_text = (
        f"📊 <b>Статистика завантажень у CRM</b>\n\n"
        f"📁 Всього файлів: {stats['total_files']}\n\n"
        f"📋 <b>За типами:</b>\n"
    )
    
    for doc_type, count in stats.get("by_type", {}).items():
        type_names = {
            "order": "📄 Накази",
            "application": "📝 Заяви",
            "certificate": "📋 Довідки",
            "termination": "❌ Звільнення",
            "contract": "📋 Договори",
            "other": "📄 Інше"
        }
        stats_text += f"{type_names.get(doc_type, '📄 ' + doc_type)}: {count}\n"
    
    if stats.get("recent_uploads"):
        stats_text += f"\n🕒 <b>Останні завантаження:</b>\n"
        for upload in stats["recent_uploads"][-3:]:
            timestamp = upload.get("timestamp", "")[:19].replace("T", " ")
            user_name = upload.get("user_name", "Unknown")
            doc_type = upload.get("doc_type", "other")
            stats_text += f"• {timestamp} — {user_name} ({doc_type})\n"
    
    await message.answer(stats_text, parse_mode="HTML")

@router.message(F.text == "📤 Завантажити в CRM")
async def upload_to_crm_menu(message: Message):
    """Меню завантаження в CRM"""
    if message.from_user.id not in [5091636029, 5063427314]:
        await message.answer("❌ Ця функція доступна лише секретарям")
        return
    
    instruction_text = (
        "📤 <b>Завантаження документів у CRM</b>\n\n"
        "👇 <b>Просто надішліть документ у цей чат:</b>\n\n"
        "📄 PDF файл — для наказів\n"
        "📷 Фото — для інших документів\n\n"
        "💡 <b>Порада:</b> Додайте підпис до документа для кращої класифікації"
    )
    
    await message.answer(instruction_text, parse_mode="HTML")
