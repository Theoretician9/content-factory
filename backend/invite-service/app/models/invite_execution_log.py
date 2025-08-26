"""
Модель логов выполнения приглашений
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM
import enum

from app.core.database import Base


class LogLevel(str, enum.Enum):
    """Уровни логирования"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ActionType(str, enum.Enum):
    """Типы действий в логах"""
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_PAUSED = "TASK_PAUSED"
    TASK_RESUMED = "TASK_RESUMED"
    INVITE_SENT = "INVITE_SENT"
    INVITE_SUCCESSFUL = "INVITE_SUCCESSFUL"
    INVITE_FAILED = "INVITE_FAILED"
    ACCOUNT_SWITCHED = "ACCOUNT_SWITCHED"
    RATE_LIMIT_HIT = "RATE_LIMIT_HIT"
    ERROR_OCCURRED = "ERROR_OCCURRED"


class InviteResultStatus(str, enum.Enum):
    """Статусы результатов приглашений"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    FLOOD_WAIT = "FLOOD_WAIT"
    ACCOUNT_BANNED = "ACCOUNT_BANNED"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    PRIVACY_RESTRICTED = "PRIVACY_RESTRICTED"
    PEER_FLOOD = "PEER_FLOOD"
    USER_NOT_MUTUAL_CONTACT = "USER_NOT_MUTUAL_CONTACT"


# PostgreSQL enum тип
invite_result_status_enum = ENUM(
    'SUCCESS', 'FAILED', 'RATE_LIMITED', 'FLOOD_WAIT', 'ACCOUNT_BANNED',
    'TARGET_NOT_FOUND', 'PRIVACY_RESTRICTED', 'PEER_FLOOD', 'USER_NOT_MUTUAL_CONTACT',
    name='inviteresultstatus',
    create_type=False
)


class InviteExecutionLog(Base):
    """Модель лога выполнения приглашений"""
    __tablename__ = "invite_execution_logs"
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, index=True, comment="Уникальный идентификатор лога")
    
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
    account_id = Column(String(255), nullable=True, comment="ID аккаунта, выполнявшего действие")
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