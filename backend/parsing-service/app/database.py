"""
Database connection and session management for PostgreSQL.
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .core.config import settings
from .models.base import Base

logger = logging.getLogger(__name__)

# Create async engine for PostgreSQL
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # SQL logging in development
    pool_size=20,         # Connection pool size
    max_overflow=30,      # Additional connections
    pool_timeout=30,      # Connection timeout
    pool_recycle=3600     # Connection recycling
)

# Create async session maker
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
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