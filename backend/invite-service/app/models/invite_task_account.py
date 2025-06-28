"""
Модель связи задач приглашений с аккаунтами
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship

from .base import BaseModel


class InviteTaskAccount(BaseModel):
    """Модель связи задачи приглашений с аккаунтом"""
    __tablename__ = "invite_task_accounts"
    
    # Связи
    task_id = Column(Integer, ForeignKey("invite_tasks.id"), nullable=False, index=True)
    account_id = Column(Integer, nullable=False, index=True, comment="ID аккаунта в Integration Service")
    
    # Статус аккаунта в задаче
    is_active = Column(Boolean, default=True, comment="Активен ли аккаунт для этой задачи")
    is_primary = Column(Boolean, default=False, comment="Основной аккаунт для задачи")
    
    # Статистика использования
    invites_sent = Column(Integer, default=0, comment="Количество отправленных приглашений")
    invites_successful = Column(Integer, default=0, comment="Количество успешных приглашений")
    invites_failed = Column(Integer, default=0, comment="Количество неудачных приглашений")
    
    # Ограничения
    max_invites_per_day = Column(Integer, default=50, comment="Максимум приглашений в день")
    current_day_invites = Column(Integer, default=0, comment="Приглашения отправленные сегодня")
    last_invite_date = Column(DateTime, nullable=True, comment="Дата последнего приглашения")
    
    # Статус и ошибки
    last_error = Column(String(500), nullable=True, comment="Последняя ошибка")
    last_error_at = Column(DateTime, nullable=True, comment="Время последней ошибки")
    consecutive_errors = Column(Integer, default=0, comment="Количество последовательных ошибок")
    
    # Настройки для этого аккаунта
    account_settings = Column(JSON, nullable=True, comment="Специфичные настройки аккаунта")
    
    # Связи
    task = relationship("InviteTask", back_populates="accounts")
    
    def __repr__(self):
        return f"<InviteTaskAccount(task_id={self.task_id}, account_id={self.account_id}, active={self.is_active})>"
    
    @property
    def can_send_invites(self) -> bool:
        """Может ли аккаунт отправлять приглашения"""
        return (
            self.is_active and 
            self.current_day_invites < self.max_invites_per_day and
            self.consecutive_errors < 5
        )
    
    @property
    def success_rate(self) -> float:
        """Процент успешных приглашений"""
        if self.invites_sent == 0:
            return 0.0
        return (self.invites_successful / self.invites_sent) * 100 