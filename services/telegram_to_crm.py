"""
Отправка документов из Telegram бота в CRM систему
"""

import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import aiofiles
from aiogram.types import Message, Document, FSInputFile

logger = logging.getLogger(__name__)

class TelegramToCRM:
    def __init__(self):
        self.crm_paths = self._get_crm_paths()
        self.ensure_crm_folders()
    
    def _get_crm_paths(self) -> Dict[str, str]:
        """Получение путей к папкам CRM"""
        return {
            "inbox": "E:/СРМ/Scans/Inbox",  # Входящие сканы для CRM
            "processed": "E:/СРМ/Scans/Processed",  # Обработанные файлы
            "orders": "E:/СРМ/Scans/Orders",  # Специальная папка для приказов из Telegram
            "temp": "E:/СРМ/Scans/Temp"  # Временные файлы
        }
    
    def ensure_crm_folders(self):
        """Создание необходимых папок в CRM"""
        for folder_name, folder_path in self.crm_paths.items():
            try:
                Path(folder_path).mkdir(parents=True, exist_ok=True)
                logger.info(f"CRM folder ensured: {folder_path}")
            except Exception as e:
                logger.error(f"Failed to create CRM folder {folder_path}: {e}")
    
    async def save_document_to_crm(self, message: Message, document: Document = None) -> bool:
        """Сохранение документа из Telegram в CRM"""
        try:
            # Определяем источник документа (файл или фото)
            if document:
                file_info = await message.bot.get_file(document.file_id)
                file_name = document.file_name or f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            elif message.photo:
                # Фото с наилучшим качеством
                file_info = await message.bot.get_file(message.photo[-1].file_id)
                file_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            elif message.document:
                file_info = await message.bot.get_file(message.document.file_id)
                file_name = message.document.file_name or f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            else:
                logger.error("No document or photo found in message")
                return False
            
            # Скачиваем файл
            temp_path = os.path.join(self.crm_paths["temp"], file_name)
            await message.bot.download_file(file_info.file_path, temp_path)
            
            # Определяем тип документа и целевую папку
            doc_type = self._classify_document(file_name, message.caption or "")
            target_folder = self._get_target_folder(doc_type)
            
            # Генерируем имя файла
            final_filename = self._generate_filename(file_name, message, doc_type)
            final_path = os.path.join(target_folder, final_filename)
            
            # Перемещаем файл в целевую папку
            shutil.move(temp_path, final_path)
            
            # Логируем операцию
            self._log_operation(message, final_path, doc_type)
            
            logger.info(f"Document saved to CRM: {final_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving document to CRM: {e}")
            return False
    
    def _classify_document(self, filename: str, caption: str) -> str:
        """Классификация типа документа"""
        filename_lower = filename.lower()
        caption_lower = caption.lower() if caption else ""
        
        # Приказы
        if any(keyword in filename_lower or keyword in caption_lower for keyword in 
               ['приказ', 'order', 'распоряжение', 'постановление']):
            return 'order'
        
        # Заявления
        elif any(keyword in filename_lower or keyword in caption_lower for keyword in 
                 ['заявление', 'statement', 'просьба']):
            return 'application'
        
        # Справки
        elif any(keyword in filename_lower or keyword in caption_lower for keyword in 
                 ['справка', 'certificate', 'reference']):
            return 'certificate'
        
        # Увольнения
        elif any(keyword in filename_lower or keyword in caption_lower for keyword in 
                 ['увольнение', 'termination', 'расчет']):
            return 'termination'
        
        # Договоры
        elif any(keyword in filename_lower or keyword in caption_lower for keyword in 
                 ['договор', 'contract', 'соглашение']):
            return 'contract'
        
        else:
            return 'other'
    
    def _get_target_folder(self, doc_type: str) -> str:
        """Получение целевой папки для типа документа"""
        if doc_type == 'order':
            return self.crm_paths["orders"]
        else:
            return self.crm_paths["inbox"]
    
    def _generate_filename(self, original_name: str, message: Message, doc_type: str) -> str:
        """Генерация имени файла для CRM"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        user_info = f"from_user_{message.from_user.id}"
        
        # Если есть подпись, используем её
        if message.caption:
            # Очищаем подпись от недопустимых символов
            clean_caption = "".join(c for c in message.caption if c.isalnum() or c in (' ', '-', '_')).rstrip()
            clean_caption = clean_caption[:50]  # Ограничиваем длину
            return f"{doc_type}_{timestamp}_{clean_caption}_{user_info}.pdf"
        else:
            # Используем оригинальное имя
            name_part = os.path.splitext(original_name)[0]
            return f"{doc_type}_{timestamp}_{name_part}_{user_info}.pdf"
    
    def _log_operation(self, message: Message, file_path: str, doc_type: str):
        """Логирование операции"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": message.from_user.id,
            "user_name": message.from_user.full_name,
            "file_path": file_path,
            "doc_type": doc_type,
            "caption": message.caption
        }
        
        # Сохраняем лог в файл
        log_file = os.path.join(self.crm_paths["processed"], "telegram_upload_log.json")
        try:
            import json
            logs = []
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            
            logs.append(log_entry)
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to log operation: {e}")
    
    async def get_upload_statistics(self) -> Dict:
        """Получение статистики загрузок"""
        try:
            stats = {
                "total_files": 0,
                "by_type": {},
                "recent_uploads": []
            }
            
            # Подсчитываем файлы в папках
            for folder_name, folder_path in self.crm_paths.items():
                if folder_name == "temp":
                    continue
                    
                if os.path.exists(folder_path):
                    files = list(Path(folder_path).glob("*"))
                    stats["total_files"] += len(files)
                    
                    for file_path in files:
                        if file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png']:
                            doc_type = self._classify_document(file_path.name, "")
                            stats["by_type"][doc_type] = stats["by_type"].get(doc_type, 0) + 1
            
            # Получаем последние загрузки из лога
            log_file = os.path.join(self.crm_paths["processed"], "telegram_upload_log.json")
            if os.path.exists(log_file):
                import json
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                
                # Берем последние 10 записей
                stats["recent_uploads"] = logs[-10:]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting upload statistics: {e}")
            return {"error": str(e)}

# Глобальный экземпляр
telegram_to_crm = None

def init_telegram_to_crm():
    """Инициализация модуля отправки в CRM"""
    global telegram_to_crm
    telegram_to_crm = TelegramToCRM()
    logger.info("Telegram to CRM module initialized")

def get_telegram_to_crm() -> Optional[TelegramToCRM]:
    """Получение экземпляра модуля"""
    return telegram_to_crm
