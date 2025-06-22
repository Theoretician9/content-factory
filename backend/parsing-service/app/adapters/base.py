"""
Base platform adapter for multi-platform parsing service.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging

from ..core.config import Platform
from ..models.parse_task import ParseTask

logger = logging.getLogger(__name__)


class BasePlatformAdapter(ABC):
    """Abstract base class for platform adapters."""
    
    def __init__(self, platform: Platform):
        self.platform = platform
        self.logger = logging.getLogger(f"{__name__}.{platform.value}")
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Get human-readable platform name."""
        pass
    
    @abstractmethod
    async def authenticate(self, account_id: str, credentials: Dict[str, Any]) -> bool:
        """Authenticate with platform using provided credentials."""
        pass
    
    @abstractmethod
    async def validate_targets(self, targets: List[str]) -> Dict[str, bool]:
        """Validate if targets exist and are accessible."""
        pass
    
    @abstractmethod
    async def parse_target(self, task: ParseTask, target: str, config: Dict[str, Any]):
        """Parse data from a target."""
        pass
    
    async def cleanup(self):
        """Clean up adapter resources."""
        self.logger.info(f"Cleaning up {self.platform_name} adapter")
    
    def normalize_target(self, target: str) -> str:
        """Normalize target identifier for the platform."""
        target = target.strip()
        if target.startswith('@'):
            target = target[1:]
        return target
    
    def __str__(self):
        return f"{self.platform_name}Adapter"
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(platform={self.platform.value})>" 