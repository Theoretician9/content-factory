"""
Базовые абстрактные интерфейсы для Platform Adapters
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass


class InviteResultStatus(str, Enum):
    """Статусы результата приглашения"""
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    FLOOD_WAIT = "flood_wait"
    PRIVACY_RESTRICTED = "privacy_restricted"
    PEER_FLOOD = "peer_flood"
    NOT_MUTUAL_CONTACT = "not_mutual_contact"
    USER_NOT_FOUND = "user_not_found"
    GROUP_NOT_FOUND = "group_not_found"
    PERMISSION_DENIED = "permission_denied"
    NETWORK_ERROR = "network_error"


class AccountStatus(str, Enum):
    """Статусы аккаунта платформы"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RATE_LIMITED = "rate_limited"
    FLOOD_WAIT = "flood_wait"
    BANNED = "banned"
    ERROR = "error"


@dataclass
class PlatformAccount:
    """Информация об аккаунте платформы"""
    account_id: int
    username: Optional[str]
    phone: Optional[str]
    status: AccountStatus
    platform: str
    
    # Лимиты и ограничения
    daily_invite_limit: int
    daily_message_limit: int
    hourly_invite_limit: int
    
    # Текущее использование
    daily_invites_used: int = 0
    daily_messages_used: int = 0
    hourly_invites_used: int = 0
    
    # Временные ограничения
    flood_wait_until: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    # Дополнительные данные
    extra_data: Optional[Dict[str, Any]] = None
    
    def can_send_invite(self) -> bool:
        """Проверка возможности отправки приглашения"""
        if self.status != AccountStatus.ACTIVE:
            return False
        
        # Проверка flood wait
        if self.flood_wait_until and datetime.utcnow() < self.flood_wait_until:
            return False
        
        # Проверка дневных лимитов
        if self.daily_invites_used >= self.daily_invite_limit:
            return False
        
        # Проверка часовых лимитов
        if self.hourly_invites_used >= self.hourly_invite_limit:
            return False
        
        return True
    
    def can_send_message(self) -> bool:
        """Проверка возможности отправки сообщения"""
        if self.status != AccountStatus.ACTIVE:
            return False
        
        if self.flood_wait_until and datetime.utcnow() < self.flood_wait_until:
            return False
        
        if self.daily_messages_used >= self.daily_message_limit:
            return False
        
        return True


@dataclass
class InviteResult:
    """Результат выполнения приглашения"""
    status: InviteResultStatus
    message: Optional[str] = None
    
    # Идентификаторы
    message_id: Optional[int] = None
    target_username: Optional[str] = None
    target_phone: Optional[str] = None
    
    # Временные данные
    sent_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    
    # Ошибки и ретраи
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_after: Optional[datetime] = None
    can_retry: bool = True
    
    # Данные платформы
    platform_response: Optional[Dict[str, Any]] = None
    account_id: Optional[int] = None
    
    @property
    def is_success(self) -> bool:
        return self.status == InviteResultStatus.SUCCESS
    
    @property
    def is_retryable(self) -> bool:
        """Можно ли повторить попытку"""
        non_retryable = [
            InviteResultStatus.PRIVACY_RESTRICTED,
            InviteResultStatus.USER_NOT_FOUND,
            InviteResultStatus.GROUP_NOT_FOUND,
            InviteResultStatus.PERMISSION_DENIED
        ]
        return self.can_retry and self.status not in non_retryable
    
    @property
    def needs_delay(self) -> bool:
        """Нужна ли задержка перед повтором"""
        return self.status in [
            InviteResultStatus.RATE_LIMITED,
            InviteResultStatus.FLOOD_WAIT,
            InviteResultStatus.PEER_FLOOD
        ]


@dataclass
class RateLimitStatus:
    """Статус rate limiting для аккаунта"""
    can_send_invite: bool
    can_send_message: bool
    
    # Оставшиеся лимиты
    invites_remaining_daily: int
    invites_remaining_hourly: int
    messages_remaining_daily: int
    
    # Время сброса лимитов
    daily_reset_at: datetime
    hourly_reset_at: datetime
    
    # Активные ограничения
    flood_wait_until: Optional[datetime] = None
    restrictions: List[str] = None
    
    def __post_init__(self):
        if self.restrictions is None:
            self.restrictions = []


class InvitePlatformAdapter(ABC):
    """Абстрактный интерфейс для адаптеров платформ приглашений"""
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
    
    @abstractmethod
    async def initialize_accounts(self, user_id: int) -> List[PlatformAccount]:
        """
        Инициализация и получение доступных аккаунтов пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список доступных аккаунтов платформы
        """
        pass
    
    @abstractmethod
    async def send_invite(
        self, 
        account: PlatformAccount, 
        target: Dict[str, Any], 
        invite_data: Dict[str, Any]
    ) -> InviteResult:
        """
        Отправка приглашения через конкретный аккаунт
        
        Args:
            account: Аккаунт для отправки
            target: Данные целевого пользователя
            invite_data: Данные приглашения (тип, группа, сообщение и т.д.)
            
        Returns:
            Результат выполнения приглашения
        """
        pass
    
    @abstractmethod
    async def send_message(
        self,
        account: PlatformAccount,
        target: Dict[str, Any],
        message_data: Dict[str, Any]
    ) -> InviteResult:
        """
        Отправка прямого сообщения
        
        Args:
            account: Аккаунт для отправки
            target: Данные получателя
            message_data: Данные сообщения
            
        Returns:
            Результат отправки сообщения
        """
        pass
    
    @abstractmethod
    async def check_rate_limits(self, account: PlatformAccount) -> RateLimitStatus:
        """
        Проверка текущих rate limits для аккаунта
        
        Args:
            account: Аккаунт для проверки
            
        Returns:
            Текущий статус лимитов
        """
        pass
    
    @abstractmethod
    async def validate_target(self, target: Dict[str, Any]) -> bool:
        """
        Валидация целевого пользователя
        
        Args:
            target: Данные цели для валидации
            
        Returns:
            True если цель валидна
        """
        pass
    
    async def handle_error(self, error: Exception, account: PlatformAccount) -> InviteResult:
        """
        Обработка ошибок платформы (может быть переопределена в наследниках)
        
        Args:
            error: Исключение от платформы
            account: Аккаунт где произошла ошибка
            
        Returns:
            Структурированный результат с ошибкой
        """
        return InviteResult(
            status=InviteResultStatus.FAILED,
            error_message=str(error),
            account_id=account.account_id,
            can_retry=True
        )
    
    async def update_account_stats(
        self, 
        account: PlatformAccount, 
        result: InviteResult
    ) -> None:
        """
        Обновление статистики аккаунта после операции
        
        Args:
            account: Аккаунт для обновления
            result: Результат операции
        """
        # Базовая реализация - может быть переопределена
        if result.is_success:
            account.daily_invites_used += 1
            account.hourly_invites_used += 1
            account.last_activity = datetime.utcnow()


class MessageResult(InviteResult):
    """Специализированный результат для сообщений"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Дополнительные поля специфичные для сообщений
        self.thread_id: Optional[int] = None
        self.reply_to_message_id: Optional[int] = None 