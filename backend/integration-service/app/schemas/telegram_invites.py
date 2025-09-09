"""
Pydantic схемы для Telegram приглашений
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, validator


class InviteType(str, Enum):
    """Типы приглашений в Telegram"""
    GROUP_INVITE = "group_invite"
    DIRECT_MESSAGE = "direct_message"


class TelegramInviteRequest(BaseModel):
    """Схема запроса на отправку Telegram приглашения"""
    invite_type: InviteType = Field(..., description="Тип приглашения")
    
    # Целевой пользователь
    target_username: Optional[str] = Field(None, description="Username цели (без @)")
    target_phone: Optional[str] = Field(None, description="Номер телефона цели")
    target_user_id: Optional[str] = Field(None, description="Telegram User ID цели")
    
    # Для group_invite
    group_id: Optional[str] = Field(None, description="ID группы/канала для приглашения")
    
    # Для direct_message
    message: Optional[str] = Field(None, max_length=4096, description="Текст сообщения")
    
    # Дополнительные параметры
    parse_mode: Optional[str] = Field("text", description="Режим парсинга (text, html)")
    silent: bool = Field(False, description="Отправить без уведомления")
    
    @model_validator(mode='after')
    def validate_target_provided(self):
        """Проверка что указан хотя бы один способ идентификации цели"""
        # Проверяем, что хотя бы одно из полей заполнено
        if self.target_username or self.target_phone or self.target_user_id:
            return self
        
        raise ValueError('Необходимо указать target_username, target_phone или target_user_id')
    
    @validator('group_id')
    def validate_group_invite_requirements(cls, v, values):
        """Проверка требований для group_invite"""
        if values.get('invite_type') == InviteType.GROUP_INVITE and not v:
            raise ValueError('group_id обязателен для group_invite')
        return v
    
    @validator('message')
    def validate_message_requirements(cls, v, values):
        """Проверка требований для direct_message"""
        if values.get('invite_type') == InviteType.DIRECT_MESSAGE and not v:
            raise ValueError('message обязательно для direct_message')
        return v


class TelegramInviteResponse(BaseModel):
    """Схема ответа на Telegram приглашение"""
    status: str = Field(..., description="Статус выполнения")
    message_id: Optional[int] = Field(None, description="ID отправленного сообщения")
    sent_at: datetime = Field(..., description="Время отправки")
    execution_time: float = Field(..., description="Время выполнения в секундах")
    
    # Информация о цели
    target_username: Optional[str] = None
    target_phone: Optional[str] = None
    invite_type: InviteType
    
    # Дополнительная информация
    error_code: Optional[str] = Field(None, description="Код ошибки если есть")
    error_message: Optional[str] = Field(None, description="Сообщение об ошибке")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TelegramMessageRequest(BaseModel):
    """Схема запроса на отправку Telegram сообщения"""
    target_entity: str = Field(..., description="Username, номер телефона или User ID получателя")
    message: str = Field(..., min_length=1, max_length=4096, description="Текст сообщения")
    parse_mode: str = Field("text", description="Режим парсинга (text, html)")
    silent: bool = Field(False, description="Отправить без уведомления")
    reply_to_message_id: Optional[int] = Field(None, description="ID сообщения для ответа")


class TelegramMessageResponse(BaseModel):
    """Схема ответа на отправку Telegram сообщения"""
    status: str = Field(..., description="Статус отправки")
    message_id: int = Field(..., description="ID отправленного сообщения")
    sent_at: datetime = Field(..., description="Время отправки")
    execution_time: float = Field(..., description="Время выполнения в секундах")
    target_entity: str = Field(..., description="Получатель сообщения")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TelegramAccountLimitsResponse(BaseModel):
    """Схема ответа с лимитами Telegram аккаунта"""
    account_id: UUID = Field(..., description="ID аккаунта")
    limits: Dict[str, Any] = Field(..., description="Лимиты аккаунта")
    current_usage: Dict[str, int] = Field(..., description="Текущее использование")
    restrictions: List[str] = Field(default_factory=list, description="Активные ограничения")
    last_updated: datetime = Field(..., description="Время последнего обновления")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TelegramFloodWaitError(BaseModel):
    """Схема для FloodWait ошибки"""
    error: str = "flood_wait"
    seconds: int = Field(..., description="Секунд до снятия ограничения")
    message: str = Field(..., description="Сообщение об ошибке")
    retry_after: datetime = Field(..., description="Время когда можно повторить запрос")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TelegramPrivacyError(BaseModel):
    """Схема для ошибки приватности"""
    error: str = "privacy_restricted"
    message: str = Field(..., description="Сообщение об ошибке")
    target: str = Field(..., description="Цель которая недоступна")


class TelegramAccountInfo(BaseModel):
    """Схема информации о Telegram аккаунте для Invite Service"""
    id: int = Field(..., description="ID аккаунта")
    username: Optional[str] = Field(None, description="Username аккаунта")
    phone: str = Field(..., description="Номер телефона")
    first_name: Optional[str] = Field(None, description="Имя")
    last_name: Optional[str] = Field(None, description="Фамилия")
    status: str = Field(..., description="Статус аккаунта")
    created_at: datetime = Field(..., description="Дата создания")
    last_activity: Optional[datetime] = Field(None, description="Последняя активность")
    daily_limits: Dict[str, int] = Field(..., description="Дневные лимиты")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 