from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta
from .base import BaseModel

class TelegramSession(BaseModel):
    """Модель для хранения Telegram сессий с Account Manager функциональностью"""
    __tablename__ = "telegram_sessions"
    
    # Основные поля (существующие)
    user_id = Column(Integer, nullable=False, index=True)
    phone = Column(String(20), nullable=False, index=True)
    session_data = Column(JSONB, nullable=False)
    session_metadata = Column(JSONB, default={})
    is_active = Column(Boolean, default=True, index=True)
    
    # Account Manager: Статус и блокировка
    status = Column(String(20), nullable=False, default='active', index=True)
    locked = Column(Boolean, nullable=False, default=False, index=True)
    locked_by = Column(String(100), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # Account Manager: Лимиты и счетчики
    used_invites_today = Column(Integer, nullable=False, default=0)
    used_messages_today = Column(Integer, nullable=False, default=0)
    contacts_today = Column(Integer, nullable=False, default=0)
    per_channel_invites = Column(JSONB, nullable=False, default={})
    
    # Account Manager: Flood и ban управление
    flood_wait_until = Column(DateTime(timezone=True), nullable=True)
    blocked_until = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    
    # Account Manager: Временные метки
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    reset_at = Column(DateTime(timezone=True), nullable=False, 
                     default=lambda: datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    
    # Ограничения
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'flood_wait', 'blocked', 'disabled')",
            name='ck_telegram_sessions_status'
        ),
    )
    
    def __repr__(self):
        return f"<TelegramSession(id={self.id}, user_id={self.user_id}, phone={self.phone}, status={self.status}, locked={self.locked})>"
    
    @property
    def is_available(self) -> bool:
        """Проверка доступности аккаунта для использования"""
        if not self.is_active or self.locked or self.status != 'active':
            return False
        
        now = datetime.utcnow()
        if self.flood_wait_until and self.flood_wait_until > now:
            return False
        
        if self.blocked_until and self.blocked_until > now:
            return False
            
        return True
    
    @property
    def daily_invite_limit(self) -> int:
        """Дневной лимит инвайтов"""
        return 30
    
    @property
    def daily_message_limit(self) -> int:
        """Дневной лимит сообщений"""
        return 30
    
    @property
    def daily_contacts_limit(self) -> int:
        """Дневной лимит добавления контактов"""
        return 15
    
    @property
    def per_channel_invite_limit(self) -> int:
        """Лимит инвайтов на один канал в день"""
        return 15
    
    @property
    def max_per_channel_total(self) -> int:
        """Максимум инвайтов на один канал (всего)"""
        return 200
    
    def can_send_invite(self, channel_id: str = None) -> bool:
        """Проверка возможности отправки инвайта"""
        if not self.is_available:
            return False
        
        # Проверка дневного лимита
        if self.used_invites_today >= self.daily_invite_limit:
            return False
        
        # Проверка лимита по каналу
        if channel_id:
            channel_invites = self.per_channel_invites.get(channel_id, {}).get('today', 0)
            if channel_invites >= self.per_channel_invite_limit:
                return False
            
            channel_total = self.per_channel_invites.get(channel_id, {}).get('total', 0)
            if channel_total >= self.max_per_channel_total:
                return False
        
        return True
    
    def can_send_message(self) -> bool:
        """Проверка возможности отправки сообщения"""
        if not self.is_available:
            return False
        
        return self.used_messages_today < self.daily_message_limit
    
    def can_add_contact(self) -> bool:
        """Проверка возможности добавления контакта"""
        if not self.is_available:
            return False
        
        return self.contacts_today < self.daily_contacts_limit 