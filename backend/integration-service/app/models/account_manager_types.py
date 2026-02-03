"""
Account Manager enums and types
Определяет все enum'ы и типы данных для Account Manager функциональности
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from uuid import UUID

class AccountStatus(str, Enum):
    """Статус аккаунта в системе Account Manager"""
    ACTIVE = "active"
    FLOOD_WAIT = "flood_wait"
    BLOCKED = "blocked"
    DISABLED = "disabled"

class ActionType(str, Enum):
    """Типы действий с аккаунтами"""
    INVITE = "invite"
    MESSAGE = "message"
    ADD_CONTACT = "add_contact"
    JOIN_CHANNEL = "join_channel"
    LEAVE_CHANNEL = "leave_channel"

class AccountPurpose(str, Enum):
    """Цель использования аккаунта"""
    INVITE_CAMPAIGN = "invite_campaign"
    MESSAGE_CAMPAIGN = "message_campaign"
    PARSING = "parsing"
    CHANNEL_MANAGEMENT = "channel_management"
    GENERAL = "general"

class ErrorType(str, Enum):
    """Типы ошибок Telegram API"""
    FLOOD_WAIT = "flood_wait"
    PEER_FLOOD = "peer_flood"
    AUTH_KEY_ERROR = "auth_key_error"
    SESSION_PASSWORD_NEEDED = "session_password_needed"
    PHONE_NUMBER_BANNED = "phone_number_banned"
    USER_DEACTIVATED = "user_deactivated"
    PRIVACY_RESTRICTED = "privacy_restricted"
    NETWORK_ERROR = "network_error"
    UNKNOWN_ERROR = "unknown_error"

@dataclass
class AccountLimits:
    """Лимиты аккаунта"""
    daily_invite_limit: int = 30
    daily_message_limit: int = 30
    contacts_daily_limit: int = 15
    per_channel_invite_limit: int = 15
    hourly_invite_limit: int = 5
    hourly_message_limit: int = 10
    invite_cooldown_minutes: int = 2
    message_cooldown_minutes: int = 1

@dataclass
class AccountUsageStats:
    """Статистика использования аккаунта"""
    invites_sent: int = 0
    messages_sent: int = 0
    contacts_added: int = 0
    channels_used: List[str] = None
    success: bool = True
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.channels_used is None:
            self.channels_used = []

@dataclass
class TelegramAccountAllocation:
    """Информация о выделенном аккаунте"""
    account_id: UUID
    user_id: int
    phone: str
    session_data: Dict[str, Any]
    allocated_at: datetime
    allocated_by: str
    purpose: AccountPurpose
    expires_at: datetime
    limits: AccountLimits
    current_usage: Dict[str, int]

@dataclass
class AccountErrorResult:
    """Результат обработки ошибки аккаунта"""
    account_id: UUID
    error_type: ErrorType
    action_taken: str
    new_status: AccountStatus
    recovery_time: Optional[datetime]
    should_retry: bool
    message: str

@dataclass
class FloodWaitInfo:
    """Информация о FloodWait"""
    account_id: UUID
    wait_until: datetime
    seconds_remaining: int
    reason: str
    can_retry_at: datetime

@dataclass
class AccountHealthStatus:
    """Статус здоровья аккаунта"""
    account_id: UUID
    is_healthy: bool
    status: AccountStatus
    issues: List[str]
    recovery_eta: Optional[datetime]
    last_check: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}