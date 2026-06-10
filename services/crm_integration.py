"""
Интеграция PML CRM с Telegram ботом
Автоматическая отправка готовых приказов в Telegram
Создание отпускных приказов через Telegram
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from aiogram import Bot
from aiogram.types import InputFile, FSInputFile
import requests

logger = logging.getLogger(__name__)

class CRMIntegration:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.crm_config = self._load_crm_config()
        
    def _load_crm_config(self) -> Dict:
        """Загрузка конфигурации CRM"""
        config_paths = [
            "E:/СРМ/pml_crm_config.json",
            "../../СРМ/pml_crm_config.json",
            "pml_crm_config.json"
        ]
        
        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load CRM config from {path}: {e}")
        
        # Конфигурация по умолчанию
        return {
            "scan_folder": "C:/PML_CRM/Scans/Inbox",
            "processed_folder": "C:/PML_CRM/Scans/Processed",
            "google_drive_folder": "PML Документы/Приказы",
            "telegram_notifications": True
        }
    
    async def send_order_to_telegram(self, order_file_path: str, order_info: Dict) -> bool:
        """Отправка приказа в Telegram"""
        try:
            if not os.path.exists(order_file_path):
                logger.error(f"Order file not found: {order_file_path}")
                return False
            
            # Получаем список всех пользователей для рассылки
            from database import SessionLocal, User
            async with SessionLocal() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(User).where(User.pml_subscribed == True)
                )
                subscribed_users = result.scalars().all()
                
                if not subscribed_users:
                    logger.info("No subscribed users found for CRM notifications")
                    return False
                
                # Подготавливаем сообщение
                message_text = self._format_order_message(order_info)
                
                # Отправляем всем подписанным пользователям
                success_count = 0
                for user in subscribed_users:
                    try:
                        # Отправляем документ
                        document = FSInputFile(order_file_path)
                        await self.bot.send_document(
                            user.telegram_id,
                            document,
                            caption=message_text,
                            parse_mode="HTML"
                        )
                        success_count += 1
                        logger.info(f"Order sent to user {user.telegram_id}")
                    except Exception as e:
                        logger.error(f"Failed to send order to {user.telegram_id}: {e}")
                
                logger.info(f"CRM order sent to {success_count}/{len(subscribed_users)} users")
                return success_count > 0
                
        except Exception as e:
            logger.error(f"Error sending order to Telegram: {e}")
            return False
    
    def _format_order_message(self, order_info: Dict) -> str:
        """Форматирование сообщения о приказе"""
        return (
            f"📄 <b>Новый приказ из CRM системы</b>\n\n"
            f"📋 <b>Тип:</b> {order_info.get('type', 'Приказ')}\n"
            f"👤 <b>Сотрудник:</b> {order_info.get('employee', 'Не указано')}\n"
            f"📅 <b>Дата:</b> {order_info.get('date', datetime.now().strftime('%d.%m.%Y'))}\n"
            f"🔢 <b>Номер:</b> {order_info.get('number', 'Без номера')}\n"
            f"📝 <b>Описание:</b> {order_info.get('description', 'Нет описания')}\n\n"
            f"📎 Документ готов к просмотру"
        )
    
    async def get_recent_orders(self, limit: int = 5) -> List[Dict]:
        """Получение последних приказов из CRM"""
        try:
            orders_folder = self.crm_config.get("processed_folder", "C:/PML_CRM/Scans/Processed")
            if not os.path.exists(orders_folder):
                return []
            
            # Ищем PDF файлы с приказами
            orders = []
            for file_path in Path(orders_folder).glob("*.pdf"):
                if "приказ" in file_path.name.lower():
                    stat = file_path.stat()
                    orders.append({
                        "file_path": str(file_path),
                        "filename": file_path.name,
                        "created_at": datetime.fromtimestamp(stat.st_ctime),
                        "size": stat.st_size
                    })
            
            # Сортируем по дате создания (новые первые)
            orders.sort(key=lambda x: x["created_at"], reverse=True)
            return orders[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent orders: {e}")
            return []
    
    async def send_recent_orders_summary(self, user_id: int) -> bool:
        """Отправка сводки последних приказов пользователю"""
        try:
            orders = await self.get_recent_orders(5)
            
            if not orders:
                await self.bot.send_message(
                    user_id,
                    "📄 <b>Последние приказы</b>\n\n"
                    "❌ Приказы не найдены в CRM системе",
                    parse_mode="HTML"
                )
                return True
            
            message = "📄 <b>Последние приказы из CRM:</b>\n\n"
            
            for i, order in enumerate(orders, 1):
                message += (
                    f"{i}. <b>{order['filename']}</b>\n"
                    f"📅 {order['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
                    f"📊 {order['size'] // 1024} КБ\n\n"
                )
            
            message += "💡 Для получения полного приказа используйте команду /get_order"
            
            await self.bot.send_message(user_id, message, parse_mode="HTML")
            return True
            
        except Exception as e:
            logger.error(f"Error sending orders summary: {e}")
            return False

# Глобальный экземпляр для использования в обработчиках
crm_integration = None

def init_crm_integration(bot: Bot):
    """Инициализация CRM интеграции"""
    global crm_integration
    crm_integration = CRMIntegration(bot)
    logger.info("CRM integration initialized")

def get_crm_integration() -> Optional[CRMIntegration]:
    """Получение экземпляра CRM интеграции"""
    return crm_integration

# Функция для вызова из CRM системы
async def notify_new_order(order_file_path: str, order_info: Dict):
    """Уведомление о новом приказе (вызывается из CRM)"""
    if crm_integration:
        await crm_integration.send_order_to_telegram(order_file_path, order_info)

class VacationOrderCreator:
    """Создание отпускных приказов через Telegram"""
    
    def __init__(self):
        self.gemini_api_key = "AQ.Ab8RN6K5B8YgGZu_zppDoVbwoPsiI5ZW_45-z6w1NdhMigK9yg"
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    
    async def create_vacation_order(self, employee_name: str, start_date: str, end_date: str, 
                                    vacation_type: str = "ежегодный", reason: str = "") -> Dict:
        """Создание отпускного приказа через Gemini"""
        try:
            # Формирование промпта для Gemini
            prompt = f"""
Создай текст приказа на отпуск в формате JSON:
{{
  "order_number": "номер_приказа",
  "order_date": "дата_приказа",
  "employee_name": "{employee_name}",
  "start_date": "{start_date}",
  "end_date": "{end_date}",
  "vacation_type": "{vacation_type}",
  "reason": "{reason}",
  "order_text": "полный_текст_приказа"
}}

Формат приказа:
ПАВЛОГРАДСЬКИЙ МІСЬКИЙ ЛІЦЕЙ
ПРИКАЗ № [номер] від [дата]
Про надання відпустки

Керуючись Законом України "Про відпустки", ПРИКАЗУЮ:

1. Надати {employee_name} {vacation_type} відпустку з {start_date} по {end_date}.
2. Відпустка надається з [причина].

Директор ліцею                 [подпис]

Верни только JSON, без дополнительного текста.
"""
            
            request_body = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 2048
                }
            }
            
            response = requests.post(
                f"{self.gemini_url}?key={self.gemini_api_key}",
                json=request_body,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Gemini API error: {response.status_code}")
            
            result = response.json()
            generated_text = result['candidates'][0]['content']['parts'][0]['text']
            order_data = json.loads(generated_text)
            
            return {
                "success": True,
                "order_data": order_data,
                "order_text": order_data.get('order_text', '')
            }
            
        except Exception as e:
            logger.error(f"Error creating vacation order: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_recent_documents(self, limit: int = 10) -> List[Dict]:
        """Получение недавно сохраненных документов из CRM"""
        try:
            # Путь к папке обработанных документов CRM
            processed_folder = "C:/PML_CRM/Scans/Processed"
            
            if not os.path.exists(processed_folder):
                return []
            
            documents = []
            for file_path in Path(processed_folder).glob("*.*"):
                if file_path.suffix.lower() in ['.pdf', '.docx', '.jpg', '.png']:
                    stat = file_path.stat()
                    documents.append({
                        "file_path": str(file_path),
                        "filename": file_path.name,
                        "created_at": datetime.fromtimestamp(stat.st_ctime),
                        "size": stat.st_size,
                        "extension": file_path.suffix
                    })
            
            # Сортируем по дате (новые первые)
            documents.sort(key=lambda x: x["created_at"], reverse=True)
            return documents[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent documents: {e}")
            return []

# Глобальный экземпляр создателя приказов
vacation_creator = VacationOrderCreator()

def get_vacation_creator() -> VacationOrderCreator:
    """Получение экземпляра создателя отпускных приказов"""
    return vacation_creator
