"""
Фабрика Platform Adapters для различных платформ
"""

from typing import Dict, Type
import logging

from .base import InvitePlatformAdapter
from .telegram import TelegramInviteAdapter

logger = logging.getLogger(__name__)


class PlatformAdapterFactory:
    """Фабрика для создания адаптеров платформ приглашений"""
    
    # Реестр зарегистрированных адаптеров
    _adapters: Dict[str, Type[InvitePlatformAdapter]] = {
        "telegram": TelegramInviteAdapter,
    }
    
    # Кэш созданных экземпляров адаптеров
    _instances: Dict[str, InvitePlatformAdapter] = {}
    
    @classmethod
    def get_adapter(cls, platform: str) -> InvitePlatformAdapter:
        """Получение адаптера для указанной платформы"""
        platform = platform.lower().strip()
        
        if platform not in cls._adapters:
            supported_platforms = ", ".join(cls._adapters.keys())
            raise ValueError(f"Платформа '{platform}' не поддерживается. Доступные: {supported_platforms}")
        
        # Возвращаем кэшированный экземпляр или создаем новый
        if platform not in cls._instances:
            adapter_class = cls._adapters[platform]
            cls._instances[platform] = adapter_class()
            logger.info(f"Создан адаптер для платформы: {platform}")
        
        return cls._instances[platform]
    
    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """Получение списка поддерживаемых платформ"""
        return list(cls._adapters.keys())


def get_platform_adapter(platform: str) -> InvitePlatformAdapter:
    """Удобная функция для получения адаптера платформы"""
    return PlatformAdapterFactory.get_adapter(platform)


def get_supported_platforms() -> list[str]:
    """Удобная функция для получения списка поддерживаемых платформ"""
    return PlatformAdapterFactory.get_supported_platforms() 