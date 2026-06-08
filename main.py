import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from database import init_db
from handlers import common_router, teacher_router, secretary_router

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
    
    logger.info("Bot started successfully!")
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.error(f"Error: {e}")
