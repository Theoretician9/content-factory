"""
WhatsApp platform adapter for parsing chats and groups (Phase 3).
"""

import logging
from typing import List, Dict, Any

from .base import BasePlatformAdapter
from ..core.config import Platform
from ..models.parse_task import ParseTask

logger = logging.getLogger(__name__)


class WhatsAppAdapter(BasePlatformAdapter):
    """WhatsApp platform adapter (Phase 3 - Not implemented yet)."""
    
    def __init__(self):
        super().__init__(Platform.WHATSAPP)
        
    @property
    def platform_name(self) -> str:
        return "WhatsApp"
    
    async def authenticate(self, account_id: str, credentials: Dict[str, Any]) -> bool:
        """WhatsApp authentication (Phase 3)."""
        self.logger.info("WhatsApp adapter not implemented yet (Phase 3)")
        return False
    
    async def validate_targets(self, targets: List[str]) -> Dict[str, bool]:
        """WhatsApp target validation (Phase 3)."""
        return {target: False for target in targets}
    
    async def parse_target(self, task: ParseTask, target: str, config: Dict[str, Any]):
        """WhatsApp parsing (Phase 3)."""
        raise NotImplementedError("WhatsApp parsing will be implemented in Phase 3") 