from sqlalchemy import Column, Integer, String, Boolean, BigInteger, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from .base import BaseModel

class TelegramChannel(BaseModel):
    """Модель для хранения Telegram каналов и групп"""
    __tablename__ = "telegram_channels"
    
    user_id = Column(Integer, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False, index=True)
    settings = Column(JSONB, default={})
    members_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    
    __table_args__ = (
        CheckConstraint(
            type.in_(['channel', 'group', 'supergroup']),
            name='valid_channel_type'
        ),
    )
    
    def __repr__(self):
        return f"<TelegramChannel(id={self.id}, user_id={self.user_id}, title={self.title}, type={self.type}, active={self.is_active})>" 