from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


_engine: AsyncEngine | None = None
_session_factory: sessionmaker | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.DATABASE_URL:
            raise RuntimeError("evolution-agent: DATABASE_URL is not configured")
        _engine = create_async_engine(settings.DATABASE_URL, future=True, echo=settings.DEBUG)
    return _engine


def get_session_factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def init_db() -> None:
    """
    Инициализация подключения к БД.

    Для MVP здесь не создаём таблицы вручную — этим займётся Alembic.
    Функция оставлена, чтобы быть совместимой с паттерном других сервисов.
    """
    _ = get_engine()


async def close_db() -> None:
    """Закрытие пула соединений."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии БД в эндпоинтах/сервисах."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session

