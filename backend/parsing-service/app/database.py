"""
Database connection and session management for PostgreSQL.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .core.config import settings
from .models.base import Base

logger = logging.getLogger(__name__)

# Create sync engine for migrations
engine = create_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"),
    echo=settings.DEBUG
)

# Create async engine for application
async_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG
)

# Create session makers
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def create_tables():
    """Create database tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created")


async def init_database():
    """Initialize database connection."""
    try:
        # Test connection
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False 