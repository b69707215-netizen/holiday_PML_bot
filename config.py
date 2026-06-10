import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///school_bot.db")
SECRETARY_TELEGRAM_ID = os.getenv("SECRETARY_TELEGRAM_ID")
# Parse multiple secretary IDs
SECRETARY_IDS = []
if SECRETARY_TELEGRAM_ID:
    SECRETARY_IDS = [int(id.strip()) for id in SECRETARY_TELEGRAM_ID.split(",") if id.strip().isdigit()]

DEFAULT_VACATION_DAYS = 24
