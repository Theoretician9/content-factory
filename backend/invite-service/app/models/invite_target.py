"""
Модель целей приглашений (контакты/пользователи для приглашения)
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
import enum

from .base import BaseModel


class TargetStatus(str, enum.Enum):
    """Статусы целей приглашений"""
    PENDING = "pending"        # Ожидает приглашения
    INVITED = "invited"        # Приглашение отправлено
    ACCEPTED = "accepted"      # Приглашение принято
    REJECTED = "rejected"      # Приглашение отклонено
    FAILED = "failed"         # Ошибка при приглашении
    BLOCKED = "blocked"       # Заблокирован
    INVALID = "invalid"       # Неверные данные контакта


class InviteTarget(BaseModel):
    """Модель цели приглашения (контакт для приглашения)"""
    __tablename__ = "invite_targets"
    
    # Связь с задачей
    task_id = Column(Integer, ForeignKey("invite_tasks.id"), nullable=False, index=True)
    
    # Данные контакта
    username = Column(String(255), nullable=True, index=True, comment="Username контакта")
    phone_number = Column(String(20), nullable=True, index=True, comment="Номер телефона")
    user_id_platform = Column(String(100), nullable=True, index=True, comment="ID пользователя на платформе")
    email = Column(String(255), nullable=True, comment="Email адрес")
    full_name = Column(String(255), nullable=True, comment="Полное имя контакта")
    
    # Дополнительные данные
    bio = Column(Text, nullable=True, comment="Биография/описание")
    profile_photo_url = Column(String(500), nullable=True, comment="URL фото профиля")
    last_seen = Column(DateTime, nullable=True, comment="Последний раз в сети")
    is_verified = Column(Boolean, default=False, comment="Верифицированный аккаунт")
    is_premium = Column(Boolean, default=False, comment="Премиум аккаунт")
    
    # Статус приглашения
    status = Column(Enum(TargetStatus), default=TargetStatus.PENDING, nullable=False, index=True)
    
    # Информация о приглашении
    invite_sent_at = Column(DateTime, nullable=True, comment="Время отправки приглашения")
    invite_response_at = Column(DateTime, nullable=True, comment="Время ответа на приглашение")
    invite_message_sent = Column(Text, nullable=True, comment="Отправленное сообщение")
    
    # Ошибки и результаты
    error_message = Column(Text, nullable=True, comment="Сообщение об ошибке")
    error_code = Column(String(50), nullable=True, comment="Код ошибки")
    attempt_count = Column(Integer, default=0, comment="Количество попыток приглашения")
    last_attempt_at = Column(DateTime, nullable=True, comment="Время последней попытки")
    
    # Аккаунт, с которого было отправлено приглашение
    sent_from_account_id = Column(Integer, nullable=True, comment="ID аккаунта, с которого отправлено")
    
    # Дополнительные метаданные
    source = Column(String(100), nullable=True, comment="Источник контакта (parsing, manual, import)")
    extra_data = Column(JSON, nullable=True, comment="Дополнительные метаданные")
    
    # Связи
    task = relationship("InviteTask", back_populates="targets")
    
    def __repr__(self):
        return f"<InviteTarget(id={self.id}, username='{self.username}', status='{self.status}')>"
    
    @property
    def primary_identifier(self) -> str:
        """Основной идентификатор контакта"""
        return self.username or self.phone_number or self.email or f"user_{self.user_id_platform}"
    
    @property
    def can_retry(self) -> bool:
        """Можно ли повторить попытку приглашения"""
        return self.status in [TargetStatus.FAILED] and self.attempt_count < 3 