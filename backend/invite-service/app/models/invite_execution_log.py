"""
Модель логов выполнения приглашений
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
import enum

from .base import BaseModel


class LogLevel(str, enum.Enum):
    """Уровни логирования"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ActionType(str, enum.Enum):
    """Типы действий в логах"""
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"
    INVITE_SENT = "invite_sent"
    INVITE_SUCCESSFUL = "invite_successful"
    INVITE_FAILED = "invite_failed"
    ACCOUNT_SWITCHED = "account_switched"
    RATE_LIMIT_HIT = "rate_limit_hit"
    ERROR_OCCURRED = "error_occurred"


class InviteExecutionLog(BaseModel):
    """Модель лога выполнения приглашений"""
    __tablename__ = "invite_execution_logs"
    
    # Связь с задачей
    task_id = Column(Integer, ForeignKey("invite_tasks.id"), nullable=False, index=True)
    
    # Связь с целью (опционально)
    target_id = Column(Integer, ForeignKey("invite_targets.id"), nullable=True, index=True)
    
    # Информация о действии
    action_type = Column(
        Enum(ActionType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True
    )
    level = Column(
        Enum(LogLevel, values_callable=lambda obj: [e.value for e in obj]),
        default=LogLevel.INFO,
        nullable=False
    )
    
    # Сообщение и детали
    message = Column(Text, nullable=False, comment="Сообщение лога")
    details = Column(JSON, nullable=True, comment="Дополнительные детали в JSON")
    
    # Контекст выполнения
    account_id = Column(Integer, nullable=True, comment="ID аккаунта, выполнявшего действие")
    worker_id = Column(String(100), nullable=True, comment="ID воркера Celery")
    execution_time_ms = Column(Integer, nullable=True, comment="Время выполнения в миллисекундах")
    
    # Ошибки
    error_code = Column(String(50), nullable=True, comment="Код ошибки")
    error_message = Column(Text, nullable=True, comment="Сообщение об ошибке")
    stack_trace = Column(Text, nullable=True, comment="Стек трейс ошибки")
    
    # Метаданные
    user_agent = Column(String(500), nullable=True, comment="User Agent (для веб запросов)")
    ip_address = Column(String(45), nullable=True, comment="IP адрес")
    
    # Связи
    task = relationship("InviteTask", back_populates="logs")
    target = relationship("InviteTarget", foreign_keys=[target_id])
    
    def __repr__(self):
        return f"<InviteExecutionLog(id={self.id}, task_id={self.task_id}, action='{self.action_type}', level='{self.level}')>"
    
    @classmethod
    def create_task_log(cls, task_id: int, action_type: ActionType, message: str, 
                       level: LogLevel = LogLevel.INFO, **kwargs):
        """Фабричный метод для создания лога задачи"""
        return cls(
            task_id=task_id,
            action_type=action_type,
            level=level,
            message=message,
            **kwargs
        )
    
    @classmethod
    def create_invite_log(cls, task_id: int, target_id: int, action_type: ActionType, 
                         message: str, account_id: int = None, level: LogLevel = LogLevel.INFO, **kwargs):
        """Фабричный метод для создания лога приглашения"""
        return cls(
            task_id=task_id,
            target_id=target_id,
            action_type=action_type,
            level=level,
            message=message,
            account_id=account_id,
            **kwargs
        ) 