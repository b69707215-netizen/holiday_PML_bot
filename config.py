import os
from dotenv import load_dotenv

load_dotenv()

# Fallbacks for Railway if env variables are not loaded from dashboard
BOT_TOKEN = os.getenv("BOT_TOKEN", "8929817821:AAGsy-296jmNKWVcFt0CCRRINcRL1HluOy4")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/bot.db")
SECRETARY_TELEGRAM_ID = os.getenv("SECRETARY_TELEGRAM_ID", "5091636029,5063427314")

# Parse multiple secretary IDs
SECRETARY_IDS = []
if SECRETARY_TELEGRAM_ID:
    SECRETARY_IDS = [int(id.strip()) for id in SECRETARY_TELEGRAM_ID.split(",") if id.strip().isdigit()]

DEFAULT_VACATION_DAYS = 24
