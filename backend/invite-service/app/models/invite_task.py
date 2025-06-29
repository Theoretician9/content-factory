"""
Модель задач приглашений
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
import enum

from .base import BaseModel


class TaskStatus(str, enum.Enum):
    """Статусы задач приглашений"""
    PENDING = "pending"          # Ожидает выполнения
    IN_PROGRESS = "in_progress"  # Выполняется
    RUNNING = "running"          # Выполняется (alias для совместимости)
    COMPLETED = "completed"      # Завершена
    FAILED = "failed"           # Ошибка
    CANCELLED = "cancelled"     # Отменена
    PAUSED = "paused"          # Приостановлена


class TaskPriority(str, enum.Enum):
    """Приоритеты задач"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class InviteTask(BaseModel):
    """Модель задачи массового приглашения"""
    __tablename__ = "invite_tasks"
    
    # Основная информация
    user_id = Column(Integer, nullable=False, index=True, comment="ID пользователя-владельца задачи")
    name = Column(String(255), nullable=False, comment="Название задачи")
    description = Column(Text, nullable=True, comment="Описание задачи")
    
    # Статус и приоритет
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    priority = Column(Enum(TaskPriority), default=TaskPriority.NORMAL, nullable=False)
    
    # Платформа и тип задачи
    platform = Column(String(50), nullable=False, index=True, comment="Платформа (telegram, instagram, whatsapp)")
    
    # Параметры выполнения
    target_count = Column(Integer, default=0, comment="Общее количество целей для приглашения")
    completed_count = Column(Integer, default=0, comment="Количество успешно выполненных приглашений")
    failed_count = Column(Integer, default=0, comment="Количество неуспешных приглашений")
    
    # Настройки задержек и лимитов
    delay_between_invites = Column(Integer, default=60, comment="Задержка между приглашениями в секундах")
    max_invites_per_account = Column(Integer, default=50, comment="Максимум приглашений с одного аккаунта")
    
    # Временные рамки
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
        return self.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.PAUSED] 