import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
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
        # If the directory exists, check write permissions
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

async def init_db():
    global engine, SessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
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
