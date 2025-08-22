"""
Конфигурация базы данных для Invite Service
"""

import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
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


def create_enum_types():
    """Создание PostgreSQL enum типов"""
    try:
        logger.info("Создание PostgreSQL enum типов...")
        
        with engine.connect() as connection:
            # Создание enum типов с проверкой существования
            enum_queries = [
                """
                DO $$ BEGIN
                    CREATE TYPE taskstatus AS ENUM (
                        'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED', 'PAUSED'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
                """,
                """
                DO $$ BEGIN
                    CREATE TYPE taskpriority AS ENUM (
                        'LOW', 'NORMAL', 'HIGH', 'URGENT'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
                """,
                """
                DO $$ BEGIN
                    CREATE TYPE targetstatus AS ENUM (
                        'PENDING', 'INVITED', 'ACCEPTED', 'REJECTED', 'FAILED', 'BLOCKED', 'INVALID'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
                """,
                """
                DO $$ BEGIN
                    CREATE TYPE targetsource AS ENUM (
                        'MANUAL', 'CSV_IMPORT', 'PARSING_IMPORT', 'API_IMPORT'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
                """,
                """
                DO $$ BEGIN
                    CREATE TYPE inviteresultstatus AS ENUM (
                        'SUCCESS', 'FAILED', 'RATE_LIMITED', 'FLOOD_WAIT', 'ACCOUNT_BANNED',
                        'TARGET_NOT_FOUND', 'PRIVACY_RESTRICTED', 'PEER_FLOOD', 'USER_NOT_MUTUAL_CONTACT'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
                """
            ]
            
            for query in enum_queries:
                connection.execute(text(query))
            
            connection.commit()
            
        logger.info("✅ PostgreSQL enum типы успешно созданы")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания enum типов: {e}")
        raise


async def create_tables():
    """Создание таблиц в базе данных"""
    try:
        logger.info("Создание таблиц в базе данных...")
        
        # Сначала создаем enum типы
        create_enum_types()
        
        # Затем создаем таблицы
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