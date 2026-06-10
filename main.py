import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from database import init_db, SessionLocal, User
from handlers import common_router, teacher_router, secretary_router, crm_router, document_upload_router
from services.crm_integration import init_crm_integration
from services.telegram_to_crm import init_telegram_to_crm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting bot...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    # Include routers
    dp.include_router(common_router)
    dp.include_router(teacher_router)
    dp.include_router(secretary_router)
    dp.include_router(crm_router)
    dp.include_router(document_upload_router)
    
    # Initialize CRM integrations
    init_crm_integration(bot)
    init_telegram_to_crm()
    logger.info("CRM integrations initialized")
    
    logger.info("Bot started successfully!")
    
    # Send startup notification to all users
    await send_startup_notification(bot)
    
    # Start polling
    await dp.start_polling(bot)

async def send_startup_notification(bot: Bot):
    """Send startup notification to all registered users"""
    async with SessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        for user in users:
            try:
                await bot.send_message(
                    user.telegram_id,
                    "🟢 <b>Бот перезапущен и готов к работе!</b>\n\n"
                    "📋 Доступные команды:\n"
                    "• /start - Главное меню\n"
                    "• /pml - Подписаться на рассылки\n"
                    "• /pml_off - Отписаться от рассылок\n\n"
                    "✅ Все функции работают в штатном режиме!",
                    parse_mode="HTML"
                )
                logger.info(f"Startup notification sent to {user.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send startup notification to {user.telegram_id}: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.error(f"Error: {e}")
