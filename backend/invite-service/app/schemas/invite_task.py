"""
Pydantic схемы для задач приглашений
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.models.invite_task import TaskStatus, TaskPriority


class TaskSettingsSchema(BaseModel):
    """Схема для дополнительных настроек задачи"""
    auto_retry_failed: bool = True
    max_retry_attempts: int = 3
    use_proxy: bool = False
    proxy_settings: Optional[Dict[str, Any]] = None
    custom_headers: Optional[Dict[str, str]] = None
    
    class Config:
        extra = "allow"  # Позволяет дополнительные поля


class InviteTaskCreate(BaseModel):
    """Схема для создания задачи приглашений"""
    name: str = Field(..., min_length=1, max_length=255, description="Название задачи")
    description: Optional[str] = Field(None, max_length=1000, description="Описание задачи")
    platform: str = Field(..., description="Платформа (telegram, instagram, whatsapp)")
    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Приоритет задачи")
    
    # Параметры выполнения
    delay_between_invites: int = Field(60, ge=30, le=3600, description="Задержка между приглашениями в секундах")
    max_invites_per_account: int = Field(50, ge=1, le=1000, description="Максимум приглашений с одного аккаунта")
    
    # Сообщение для приглашения
    invite_message: Optional[str] = Field(None, max_length=1000, description="Текст сообщения при приглашении")
    
    # Временные рамки
    scheduled_start: Optional[datetime] = Field(None, description="Запланированное время начала")
    
    # Дополнительные настройки
    settings: Optional[TaskSettingsSchema] = Field(None, description="Дополнительные настройки задачи")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class InviteTaskUpdate(BaseModel):
    """Схема для обновления задачи приглашений"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    
    delay_between_invites: Optional[int] = Field(None, ge=30, le=3600)
    max_invites_per_account: Optional[int] = Field(None, ge=1, le=1000)
    invite_message: Optional[str] = Field(None, max_length=1000)
    scheduled_start: Optional[datetime] = None
    settings: Optional[TaskSettingsSchema] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class InviteTaskResponse(BaseModel):
    """Схема для ответа с задачей приглашений"""
    id: int
    user_id: int
    name: str
    description: Optional[str]
    
    status: TaskStatus
    priority: TaskPriority
    platform: str
    
    # Статистика
    target_count: int
    completed_count: int
    failed_count: int
    progress_percentage: float
    
    # Параметры
    delay_between_invites: int
    max_invites_per_account: int
    invite_message: Optional[str]
    
    # Временные рамки
    created_at: datetime
    updated_at: datetime
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    scheduled_start: Optional[datetime]
    
    # Ошибки
    error_message: Optional[str]
    
    # Дополнительные данные
    settings: Optional[Dict[str, Any]]
    results: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 