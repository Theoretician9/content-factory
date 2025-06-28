"""
Pydantic схемы для целевых контактов (targets)
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, validator

from app.models.invite_target import TargetStatus


class TargetSource(str, Enum):
    """Источники целевых контактов"""
    MANUAL = "manual"          # Ручное добавление
    IMPORT = "import"          # Импорт из файла
    PARSING = "parsing"        # Из результатов парсинга
    API = "api"               # Через API


class TargetSortBy(str, Enum):
    """Поля для сортировки целей"""
    CREATED_AT = "created_at"
    USERNAME = "username"
    STATUS = "status"
    LAST_ATTEMPT = "last_attempt_at"
    ATTEMPT_COUNT = "attempt_count"


class InviteTargetCreate(BaseModel):
    """Схема для создания цели приглашения"""
    username: Optional[str] = Field(None, max_length=255, description="Username контакта")
    phone_number: Optional[str] = Field(None, max_length=20, description="Номер телефона")
    user_id_platform: Optional[str] = Field(None, max_length=100, description="ID пользователя на платформе")
    email: Optional[str] = Field(None, max_length=255, description="Email адрес")
    full_name: Optional[str] = Field(None, max_length=255, description="Полное имя")
    
    # Дополнительные данные
    bio: Optional[str] = Field(None, description="Биография")
    profile_photo_url: Optional[str] = Field(None, max_length=500, description="URL фото профиля")
    source: TargetSource = Field(TargetSource.MANUAL, description="Источник контакта")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="Дополнительные данные")
    
    @validator('username', 'phone_number', 'user_id_platform', 'email')
    def at_least_one_identifier(cls, v, values):
        """Проверяем что есть хотя бы один идентификатор"""
        identifiers = [
            values.get('username'),
            values.get('phone_number'), 
            values.get('user_id_platform'),
            values.get('email')
        ]
        if v is None and all(id is None for id in identifiers):
            raise ValueError('Необходим хотя бы один идентификатор: username, phone_number, user_id_platform или email')
        return v


class InviteTargetBulkCreate(BaseModel):
    """Схема для массового создания целей"""
    targets: List[InviteTargetCreate] = Field(..., min_items=1, max_items=1000, description="Список целей для создания")
    source: TargetSource = Field(TargetSource.IMPORT, description="Источник всех целей")
    skip_duplicates: bool = Field(True, description="Пропускать дубликаты")
    validate_before_insert: bool = Field(True, description="Валидировать перед вставкой")


class InviteTargetUpdate(BaseModel):
    """Схема для обновления цели приглашения"""
    username: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=20)
    user_id_platform: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    profile_photo_url: Optional[str] = Field(None, max_length=500)
    status: Optional[TargetStatus] = None
    extra_data: Optional[Dict[str, Any]] = None


class InviteTargetResponse(BaseModel):
    """Схема для ответа с целью приглашения"""
    id: int
    task_id: int
    
    # Данные контакта
    username: Optional[str]
    phone_number: Optional[str]
    user_id_platform: Optional[str]
    email: Optional[str]
    full_name: Optional[str]
    bio: Optional[str]
    profile_photo_url: Optional[str]
    
    # Статус и метаданные
    status: TargetStatus
    source: Optional[str]
    primary_identifier: str
    can_retry: bool
    
    # Информация о приглашении
    invite_sent_at: Optional[datetime]
    invite_response_at: Optional[datetime]
    invite_message_sent: Optional[str]
    
    # Ошибки и попытки
    error_message: Optional[str]
    error_code: Optional[str]
    attempt_count: int
    last_attempt_at: Optional[datetime]
    sent_from_account_id: Optional[int]
    
    # Временные метки
    created_at: datetime
    updated_at: datetime
    
    # Дополнительные данные
    extra_data: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TargetFilterSchema(BaseModel):
    """Схема для фильтрации целей"""
    status: Optional[List[TargetStatus]] = Field(None, description="Фильтр по статусам")
    source: Optional[List[TargetSource]] = Field(None, description="Фильтр по источникам")
    has_username: Optional[bool] = Field(None, description="Есть ли username")
    has_phone: Optional[bool] = Field(None, description="Есть ли телефон")
    created_after: Optional[datetime] = Field(None, description="Созданы после даты")
    created_before: Optional[datetime] = Field(None, description="Созданы до даты")
    search: Optional[str] = Field(None, description="Поиск по username/имени/email")
    
    # Пагинация
    page: int = Field(1, ge=1, description="Номер страницы")
    page_size: int = Field(50, ge=1, le=200, description="Размер страницы")
    
    # Сортировка
    sort_by: TargetSortBy = Field(TargetSortBy.CREATED_AT, description="Поле для сортировки")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Порядок сортировки")


class TargetListResponse(BaseModel):
    """Схема для списка целей с пагинацией"""
    items: List[InviteTargetResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    
    # Статистика по статусам
    status_counts: Dict[str, int]


class TargetImportSchema(BaseModel):
    """Схема для импорта целей из файла"""
    file_type: str = Field(..., regex="^(csv|xlsx|json)$", description="Тип файла")
    column_mapping: Dict[str, str] = Field(..., description="Маппинг колонок файла на поля модели")
    skip_header: bool = Field(True, description="Пропустить первую строку (заголовок)")
    skip_duplicates: bool = Field(True, description="Пропускать дубликаты")
    validate_before_insert: bool = Field(True, description="Валидировать перед вставкой")
    batch_size: int = Field(100, ge=1, le=1000, description="Размер батча для вставки")


class TargetImportResult(BaseModel):
    """Результат импорта целей"""
    total_processed: int
    created_count: int
    skipped_count: int
    error_count: int
    errors: List[Dict[str, Any]]
    duration_seconds: float
    
    
class TargetBulkAction(str, Enum):
    """Массовые действия с целями"""
    DELETE = "delete"
    RESET_STATUS = "reset_status" 
    SET_STATUS = "set_status"
    RETRY = "retry"


class TargetBulkRequest(BaseModel):
    """Схема для массовых операций с целями"""
    target_ids: List[int] = Field(..., min_items=1, description="Список ID целей")
    action: TargetBulkAction = Field(..., description="Действие")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Дополнительные параметры")


class TargetStatsResponse(BaseModel):
    """Статистика по целям задачи"""
    total_targets: int
    status_breakdown: Dict[str, int]
    success_rate: float
    average_attempts: float
    
    # Статистика по времени
    total_time_spent: Optional[float]  # в секундах
    average_time_per_invite: Optional[float]
    
    # Топ ошибок
    top_errors: List[Dict[str, Any]]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 