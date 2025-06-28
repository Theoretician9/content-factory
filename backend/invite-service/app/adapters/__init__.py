"""
Platform Adapters для различных платформ приглашений
"""

from .base import (
    InvitePlatformAdapter,
    PlatformAccount,
    InviteResult,
    RateLimitStatus,
    InviteResultStatus,
    AccountStatus
)
from .telegram import TelegramInviteAdapter
from .factory import PlatformAdapterFactory, get_platform_adapter, get_supported_platforms

__all__ = [
    # Базовые классы
    "InvitePlatformAdapter",
    "PlatformAccount",
    "InviteResult",
    "RateLimitStatus",
    "InviteResultStatus",
    "AccountStatus",
    
    # Адаптеры платформ
    "TelegramInviteAdapter",
    
    # Фабрика
    "PlatformAdapterFactory",
    "get_platform_adapter",
    "get_supported_platforms",
] 