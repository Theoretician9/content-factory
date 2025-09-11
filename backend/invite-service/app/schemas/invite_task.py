"""
Pydantic схемы для задач приглашений
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from app.models.invite_task import TaskStatus, TaskPriority


class SortOrder(str, Enum):
    """Порядок сортировки"""
    ASC = "asc"
    DESC = "desc"


class TaskSortBy(str, Enum):
    """Поля для сортировки задач"""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    NAME = "name"
    PRIORITY = "priority"
    STATUS = "status"
    PROGRESS = "progress_percentage"


class TaskSettingsSchema(BaseModel):
    """Схема для дополнительных настроек задачи"""
    auto_retry_failed: bool = True
    max_retry_attempts: int = 3
    use_proxy: bool = False
    proxy_settings: Optional[Dict[str, Any]] = None
    custom_headers: Optional[Dict[str, str]] = None
    
    # Настройки для Telegram приглашений
    group_id: Optional[str] = Field(None, description="ID группы/канала для приглашений")
    invite_type: Optional[str] = Field("group_invite", description="Тип приглашения")
    
    class Config:
        extra = "allow"  # Позволяет дополнительные поля


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


class TaskFilterSchema(BaseModel):
    """Схема для фильтрации задач"""
    status: Optional[List[TaskStatus]] = Field(None, description="Фильтр по статусам")
    platform: Optional[List[str]] = Field(None, description="Фильтр по платформам")
    priority: Optional[List[TaskPriority]] = Field(None, description="Фильтр по приоритетам")
    created_after: Optional[datetime] = Field(None, description="Созданы после даты")
    created_before: Optional[datetime] = Field(None, description="Созданы до даты")
    name_contains: Optional[str] = Field(None, description="Содержит в названии")
    
    # Пагинация
    page: int = Field(1, ge=1, description="Номер страницы")
    page_size: int = Field(20, ge=1, le=100, description="Размер страницы")
    
    # Сортировка
    sort_by: TaskSortBy = Field(TaskSortBy.CREATED_AT, description="Поле для сортировки")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Порядок сортировки")


class TaskListResponse(BaseModel):
    """Схема для списка задач с пагинацией"""
    items: List[InviteTaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class TaskDuplicateRequest(BaseModel):
    """Схема для дублирования задачи"""
    new_name: str = Field(..., min_length=1, max_length=255, description="Название новой задачи")
    copy_targets: bool = Field(True, description="Копировать целевую аудиторию")
    copy_settings: bool = Field(True, description="Копировать настройки")
    reset_schedule: bool = Field(True, description="Сбросить запланированное время")


class TaskBulkAction(str, Enum):
    """Массовые действия с задачами"""
    DELETE = "delete"
    PAUSE = "pause"
    RESUME = "resume" 
    CANCEL = "cancel"
    SET_PRIORITY = "set_priority"


class TaskBulkRequest(BaseModel):
    """Схема для массовых операций"""
    task_ids: List[int] = Field(..., min_items=1, description="Список ID задач")
    action: TaskBulkAction = Field(..., description="Действие")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Дополнительные параметры")


class InviteTaskCreate(BaseModel):
    """Схема для создания задачи приглашений"""
    name: str = Field(..., min_length=1, max_length=255, description="Название задачи")
    description: Optional[str] = Field(None, max_length=1000, description="Описание задачи")
    platform: str = Field(..., description="Платформа (telegram, instagram, whatsapp)")
    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Приоритет задачи")
    
    # ❌ УДАЛЕНО: Все лимиты управляются только Account Manager согласно ТЗ
    # Invite Service не должен иметь собственных лимитов
    
    # Сообщение для приглашения
    invite_message: Optional[str] = Field(None, max_length=1000, description="Текст сообщения при приглашении")
    
    # Временные рамки
    scheduled_start: Optional[datetime] = Field(None, description="Запланированное время начала")
    
    # Дополнительные настройки
    settings: Optional[TaskSettingsSchema] = Field(None, description="Дополнительные настройки задачи")
    
    @field_validator('priority', mode='before')
    @classmethod
    def validate_priority(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v
    
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
    
    # ❌ УДАЛЕНО: Все лимиты управляются только Account Manager согласно ТЗ
    # Invite Service не должен иметь собственных лимитов
    
    invite_message: Optional[str] = Field(None, max_length=1000)
    scheduled_start: Optional[datetime] = None
    settings: Optional[TaskSettingsSchema] = None
    
    @field_validator('priority', 'status', mode='before')
    @classmethod
    def validate_enums(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }