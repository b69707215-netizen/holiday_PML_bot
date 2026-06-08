import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///school_bot.db")
SECRETARY_TELEGRAM_ID = os.getenv("SECRETARY_TELEGRAM_ID")

DEFAULT_VACATION_DAYS = 24
