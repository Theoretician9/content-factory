from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from typing import AsyncGenerator
import logging

from .core.config import get_settings
from .models.base import Base

logger = logging.getLogger(__name__)

settings = get_settings()

# Async engine для основной работы
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20
)

# Sync engine для миграций и админских операций
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Session makers
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Получение асинхронной сессии для работы с БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

def get_sync_session():
    """Получение синхронной сессии для миграций"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database sync session error: {e}")
        raise
    finally:
        session.close()

async def init_db():
    """Инициализация базы данных"""
    try:
        async with async_engine.begin() as conn:
            # Создаем таблицы если их нет
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

async def close_db():
    """Закрытие соединения с базой данных"""
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("Database connections closed") 