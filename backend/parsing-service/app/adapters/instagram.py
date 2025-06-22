"""
Instagram platform adapter for parsing posts and profiles (Phase 2).
"""

import logging
from typing import List, Dict, Any

from .base import BasePlatformAdapter
from ..core.config import Platform
from ..models.parse_task import ParseTask

logger = logging.getLogger(__name__)


class InstagramAdapter(BasePlatformAdapter):
    """Instagram platform adapter (Phase 2 - Not implemented yet)."""
    
    def __init__(self):
        super().__init__(Platform.INSTAGRAM)
        
    @property
    def platform_name(self) -> str:
        return "Instagram"
    
    async def authenticate(self, account_id: str, credentials: Dict[str, Any]) -> bool:
        """Instagram authentication (Phase 2)."""
        self.logger.info("Instagram adapter not implemented yet (Phase 2)")
        return False
    
    async def validate_targets(self, targets: List[str]) -> Dict[str, bool]:
        """Instagram target validation (Phase 2)."""
        self.logger.info("Instagram adapter not implemented yet (Phase 2)")
        return {target: False for target in targets}
    
    async def parse_target(self, task: ParseTask, target: str, config: Dict[str, Any]):
        """Instagram parsing (Phase 2)."""
        self.logger.info("Instagram adapter not implemented yet (Phase 2)")
        raise NotImplementedError("Instagram parsing will be implemented in Phase 2") 