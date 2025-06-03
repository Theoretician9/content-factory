from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from .base import BaseModel

class TelegramSession(BaseModel):
    """Модель для хранения Telegram сессий"""
    __tablename__ = "telegram_sessions"
    
    user_id = Column(Integer, nullable=False, index=True)
    phone = Column(String(20), nullable=False, index=True)
    session_data = Column(JSONB, nullable=False)
    metadata = Column(JSONB, default={})
    is_active = Column(Boolean, default=True, index=True)
    
    def __repr__(self):
        return f"<TelegramSession(id={self.id}, user_id={self.user_id}, phone={self.phone}, active={self.is_active})>" 