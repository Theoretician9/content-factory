from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, UUID
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class BaseModel(Base):
    """Базовая модель с общими полями"""
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) 