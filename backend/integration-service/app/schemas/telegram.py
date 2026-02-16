from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import re

from .base import BaseModelResponse

# Схемы для аутентификации
class TelegramAuthRequest(BaseModel):
    """Схема запроса на подключение Telegram аккаунта"""
    phone: str = Field(..., description="Номер телефона в международном формате")
    password: Optional[str] = Field(None, description="Пароль для 2FA (если требуется)")
    code: Optional[str] = Field(None, description="Код подтверждения из SMS/Telegram")
    
    @validator('phone')
    def validate_phone(cls, v):
        """Валидация номера телефона"""
        # Убираем все нецифровые символы кроме +
        phone = re.sub(r'[^\d+]', '', v)
        
        # Проверяем формат
        if not re.match(r'^\+\d{10,15}$', phone):
            raise ValueError('Неверный формат номера телефона. Используйте международный формат: +1234567890')
        
        return phone

class TelegramConnectResponse(BaseModel):
    """Схема ответа на запрос подключения"""
    status: str = Field(..., description="Статус подключения: pending, code_required, 2fa_required, success")
    session_id: Optional[UUID] = Field(None, description="ID сессии")
    message: str = Field(..., description="Описание статуса")
    qr_code: Optional[str] = Field(None, description="QR код для входа (base64)")

class TelegramQRCheckRequest(BaseModel):
    """Схема запроса проверки QR авторизации с опциональным 2FA паролем"""
    password: Optional[str] = Field(None, description="Пароль для 2FA (если требуется)")

# Схемы для сессий
class TelegramSessionCreate(BaseModel):
    """Схема создания Telegram сессии"""
    phone: str
    session_data: Dict[str, Any]
    session_metadata: Optional[Dict[str, Any]] = {}

class TelegramSessionResponse(BaseModelResponse):
    """Схема ответа с данными сессии"""
    user_id: int
    phone: str
    session_metadata: Dict[str, Any]
    is_active: bool

# Схемы для ботов
class TelegramBotCreate(BaseModel):
    """Схема создания Telegram бота"""
    bot_token: str = Field(..., description="Токен бота")
    settings: Optional[Dict[str, Any]] = {}
    
    @validator('bot_token')
    def validate_bot_token(cls, v):
        """Валидация токена бота"""
        if not re.match(r'^\d+:[\w-]+$', v):
            raise ValueError('Неверный формат токена бота. Ожидается формат: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz')
        return v

class TelegramBotResponse(BaseModelResponse):
    """Схема ответа с данными бота"""
    user_id: int
    bot_token: str
    username: str
    settings: Dict[str, Any]
    is_active: bool

# Схемы для каналов
class TelegramChannelCreate(BaseModel):
    """Схема создания/добавления канала"""
    channel_id: int = Field(..., description="ID канала/группы")
    title: str = Field(..., description="Название канала/группы")
    type: str = Field(..., description="Тип: channel, group, supergroup")
    settings: Optional[Dict[str, Any]] = {}
    
    @validator('type')
    def validate_channel_type(cls, v):
        """Валидация типа канала"""
        if v not in ['channel', 'group', 'supergroup']:
            raise ValueError('Тип должен быть: channel, group или supergroup')
        return v

class TelegramChannelResponse(BaseModelResponse):
    """Схема ответа с данными канала"""
    user_id: int
    channel_id: int
    title: str
    type: str
    settings: Dict[str, Any]
    members_count: int
    is_active: bool

# Схемы для отправки сообщений
class SendMessageRequest(BaseModel):
    """Схема запроса на отправку сообщения.

    Для удобства evolution-agent и других клиентов допускает как numeric channel_id,
    так и строковый идентификатор/ссылку на канал:
    - 123456789
    - @my_channel
    - https://t.me/my_channel
    """

    text: str = Field(..., max_length=4096, description="Текст сообщения")
    # ID канала/чата в Telegram, от имени которого отправляется сообщение
    channel_id: Optional[int] = Field(
        None,
        description="Telegram channel/group ID для отправки сообщения (numeric chat_id)",
    )
    # Дополнительное строковое представление канала: username или t.me‑ссылка
    channel: Optional[str] = Field(
        None,
        description="Telegram канал в виде @username или t.me/…; "
        "будет автоматически нормализован в numeric channel_id",
    )
    parse_mode: Optional[str] = Field("HTML", description="Режим парсинга: HTML, Markdown, MarkdownV2")
    disable_web_page_preview: Optional[bool] = Field(False, description="Отключить предпросмотр ссылок")

    @validator("channel_id", always=True)
    def validate_channel_inputs(cls, v, values):  # type: ignore[override]
        """
        Гарантирует, что хотя бы один из идентификаторов канала передан.
        """
        channel = values.get("channel")
        if v is None and (channel is None or not str(channel).strip()):
            raise ValueError("Either channel_id or channel must be provided")
        return v
class SendMessageResponse(BaseModel):
    """Схема ответа на отправку сообщения"""
    success: bool
    message_id: Optional[int] = None
    error: Optional[str] = None

# Схемы для списков
class TelegramSessionList(BaseModel):
    """Список сессий с пагинацией"""
    sessions: list[TelegramSessionResponse]
    total: int
    page: int
    size: int

class TelegramBotList(BaseModel):
    """Список ботов с пагинацией"""
    bots: list[TelegramBotResponse]
    total: int
    page: int
    size: int

class TelegramChannelList(BaseModel):
    """Список каналов с пагинацией"""
    channels: list[TelegramChannelResponse]
    total: int
    page: int
    size: int 