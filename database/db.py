import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from database.models import Base
from config import DATABASE_URL

db_url = DATABASE_URL

# 1. Ensure database directory exists
if db_url.startswith("sqlite://"):
    clean_url = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    if clean_url:
        db_dir = os.path.dirname(clean_url)
        if db_dir:
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                print(f"Warning: Failed to create database directory {db_dir}: {e}")

# 2. Verify write access to the directory
try:
    clean_url = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    if clean_url:
        db_dir = os.path.dirname(clean_url) or "."
        if os.path.exists(db_dir):
            if not os.access(db_dir, os.W_OK):
                raise PermissionError(f"Directory {db_dir} is not writable")
        else:
            raise FileNotFoundError(f"Directory {db_dir} does not exist")
except Exception as e:
    print(f"Warning: Database path is not writable ({e}). Falling back to local school_bot.db")
    db_url = "sqlite:///school_bot.db"

engine = create_async_engine(
    db_url.replace("sqlite://", "sqlite+aiosqlite://"),
    echo=False
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def _run_migrations(conn):
    """Додаємо нові колонки якщо їх ще немає (SQLite ALTER TABLE)"""
    # Додати appointed_by якщо відсутнє
    try:
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN appointed_by INTEGER REFERENCES users(id)"
        ))
        print("Migration: added column 'appointed_by' to users")
    except Exception:
        pass  # Колонка вже існує — ігноруємо

    # Додати username якщо відсутнє
    try:
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN username VARCHAR(255)"
        ))
        print("Migration: added column 'username' to users")
    except Exception:
        pass  # вже є

    # Оновити enum: SQLite зберігає як TEXT — нові значення просто запишуться
    # Нічого додаткового не потрібно для DIRECTOR/VICE_PRINCIPAL

async def init_db():
    global engine, SessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _run_migrations(conn)
    except Exception as e:
        print(f"Warning: Failed to initialize DB with {db_url} ({e}). Falling back to local school_bot.db")
        db_url_fallback = "sqlite:///school_bot.db"
        engine = create_async_engine(
            db_url_fallback.replace("sqlite://", "sqlite+aiosqlite://"),
            echo=False
        )
        SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _run_migrations(conn)
