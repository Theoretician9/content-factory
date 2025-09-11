"""
Модель задач приглашений
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class TaskStatus(str, enum.Enum):
    """Статусы задач приглашений"""
    PENDING = "PENDING"          # Ожидает выполнения
    IN_PROGRESS = "IN_PROGRESS"  # Выполняется
    COMPLETED = "COMPLETED"      # Завершена
    FAILED = "FAILED"           # Ошибка
    CANCELLED = "CANCELLED"     # Отменена
    PAUSED = "PAUSED"          # Приостановлена


class TaskPriority(str, enum.Enum):
    """Приоритеты задач"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


# PostgreSQL enum типы
task_status_enum = ENUM(
    'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED', 'PAUSED',
    name='taskstatus',
    create_type=False
)

task_priority_enum = ENUM(
    'LOW', 'NORMAL', 'HIGH', 'URGENT',
    name='taskpriority', 
    create_type=False
)


class InviteTask(Base):
    """Модель задачи массового приглашения"""
    __tablename__ = "invite_tasks"
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, index=True, comment="Уникальный идентификатор задачи")
    
    # Основная информация
    user_id = Column(Integer, nullable=False, index=True, comment="ID пользователя-владельца задачи")
    name = Column(String(255), nullable=False, comment="Название задачи")
    description = Column(Text, nullable=True, comment="Описание задачи")
    
    # Статус и приоритет
    status = Column(
        task_status_enum,
        default=TaskStatus.PENDING.value,
        nullable=False,
        index=True
    )
    priority = Column(
        task_priority_enum,
        default=TaskPriority.NORMAL.value,
        nullable=False
    )
    
    # Платформа и тип задачи
    platform = Column(String(50), nullable=False, index=True, comment="Платформа (telegram, instagram, whatsapp)")
    
    # Параметры выполнения
    target_count = Column(Integer, default=0, comment="Общее количество целей для приглашения")
    completed_count = Column(Integer, default=0, comment="Количество успешно выполненных приглашений")
    failed_count = Column(Integer, default=0, comment="Количество неуспешных приглашений")
    
    # Настройки задержек и лимитов (согласно ТЗ Account Manager)
    delay_between_invites = Column(Integer, default=600, comment="Задержка между приглашениями в секундах (10-15 минут согласно ТЗ Account Manager)")
    max_invites_per_account = Column(Integer, default=15, comment="Максимум приглашений с одного аккаунта в день (согласно ТЗ Account Manager)")
    
    # Временные рамки
    created_at = Column(DateTime, server_default=func.now(), default=func.now(), nullable=False, comment="Время создания задачи")
    updated_at = Column(DateTime, server_default=func.now(), default=func.now(), onupdate=func.now(), nullable=False, comment="Время последнего обновления")
    start_time = Column(DateTime, nullable=True, comment="Время начала выполнения задачи")
    end_time = Column(DateTime, nullable=True, comment="Время окончания выполнения задачи")
    scheduled_start = Column(DateTime, nullable=True, comment="Запланированное время начала")
    
    # Сообщение для приглашения
    invite_message = Column(Text, nullable=True, comment="Текст сообщения при приглашении")
    
    # Дополнительные параметры в JSON
    settings = Column(JSON, nullable=True, comment="Дополнительные настройки задачи")
    
    # Результаты и ошибки
    error_message = Column(Text, nullable=True, comment="Сообщение об ошибке")
    results = Column(JSON, nullable=True, comment="Детальные результаты выполнения")
    
    # Связи с другими таблицами
    targets = relationship("InviteTarget", back_populates="task", cascade="all, delete-orphan")
    accounts = relationship("InviteTaskAccount", back_populates="task", cascade="all, delete-orphan")
    logs = relationship("InviteExecutionLog", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<InviteTask(id={self.id}, name='{self.name}', status='{self.status}', platform='{self.platform}')>"
    
    @property
    def progress_percentage(self) -> float:
        """Процент выполнения задачи"""
        if self.target_count == 0:
            return 0.0
        return (self.completed_count / self.target_count) * 100
    
    @property
    def is_active(self) -> bool:
        """Проверка, активна ли задача"""
        return self.status in [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED] 