"""
Конфигурация базы данных для Invite Service
"""

import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

# Создание движка базы данных
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.DEBUG
)

# Создание фабрики сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()


async def create_tables():
    """Создание таблиц в базе данных"""
    try:
        logger.info("Создание таблиц в базе данных...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Таблицы успешно созданы")
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")
        raise


def get_db():
    """Получение сессии базы данных (для FastAPI dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """Получение сессии базы данных (для Celery воркеров)"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close() 