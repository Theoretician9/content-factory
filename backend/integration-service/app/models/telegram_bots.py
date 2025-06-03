from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from .base import BaseModel

class TelegramBot(BaseModel):
    """Модель для хранения Telegram ботов"""
    __tablename__ = "telegram_bots"
    
    user_id = Column(Integer, nullable=False, index=True)
    bot_token = Column(String(100), nullable=False)
    username = Column(String(50), nullable=False, index=True)
    settings = Column(JSONB, default={})
    is_active = Column(Boolean, default=True, index=True)
    
    def __repr__(self):
        return f"<TelegramBot(id={self.id}, user_id={self.user_id}, username={self.username}, active={self.is_active})>" 