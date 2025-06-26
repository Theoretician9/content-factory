"""
Database connection and session management for MySQL.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .core.config import settings
from .models.base import Base

logger = logging.getLogger(__name__)

# Create sync engine for migrations (MySQL)
sync_url = settings.DATABASE_URL
if sync_url.startswith("mysql://"):
    sync_url = sync_url.replace("mysql://", "mysql+pymysql://")

engine = create_engine(
    sync_url,
    echo=settings.DEBUG
)

# Create async engine for application (MySQL) 
async_url = settings.DATABASE_URL
if async_url.startswith("mysql://"):
    async_url = async_url.replace("mysql://", "mysql+aiomysql://")

async_engine = create_async_engine(
    async_url,
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