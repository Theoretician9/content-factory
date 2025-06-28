"""
Базовые модели для Invite Service
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, func
from app.core.database import Base


class BaseModel(Base):
    """Базовая модель с общими полями"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False) 