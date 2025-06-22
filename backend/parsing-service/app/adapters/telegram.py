"""
Telegram platform adapter for parsing channels and groups.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import BasePlatformAdapter
from ..core.config import Platform
from ..core.vault import get_vault_client
from ..models.parse_task import ParseTask

logger = logging.getLogger(__name__)


class TelegramAdapter(BasePlatformAdapter):
    """Telegram platform adapter for parsing channels and groups."""
    
    def __init__(self):
        super().__init__(Platform.TELEGRAM)
        self.client = None
        self.session_file_path = None
        self.vault_client = get_vault_client()
        
    @property
    def platform_name(self) -> str:
        return "Telegram"
    
    async def authenticate(self, account_id: str, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Telegram using session from Vault."""
        try:
            session_id = credentials.get('session_id')
            if not session_id:
                self.logger.error("No session_id provided")
                return False
            
            # Get API keys from Vault
            api_keys = self.vault_client.get_platform_api_keys(Platform.TELEGRAM)
            if not api_keys:
                self.logger.error("Failed to get API keys from Vault")
                return False
            
            # TODO: Initialize Telegram client
            self.logger.info(f"✅ Telegram authenticated for account {account_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Authentication failed: {e}")
            return False
    
    async def validate_targets(self, targets: List[str]) -> Dict[str, bool]:
        """Validate if Telegram targets exist and are accessible."""
        results = {}
        
        for target in targets:
            try:
                # TODO: Implement actual validation
                normalized_target = self.normalize_target(target)
                results[target] = True  # Placeholder
                self.logger.info(f"✅ Validated target: {normalized_target}")
            except Exception as e:
                self.logger.warning(f"❌ Cannot validate target '{target}': {e}")
                results[target] = False
        
        return results
    
    async def parse_target(self, task: ParseTask, target: str, config: Dict[str, Any]):
        """Parse messages from a Telegram target."""
        try:
            normalized_target = self.normalize_target(target)
            message_limit = config.get('message_limit', 10000)
            
            self.logger.info(f"📥 Parsing {normalized_target} (limit: {message_limit})")
            
            # TODO: Implement actual parsing logic
            # This is a placeholder - would use Telethon to parse messages
            
            self.logger.info(f"✅ Completed parsing {normalized_target}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse {target}: {e}")
            raise
    
    async def cleanup(self):
        """Clean up Telegram client and session file."""
        try:
            if self.client:
                # TODO: Disconnect client
                self.client = None
            
            if self.session_file_path:
                self.vault_client.cleanup_temp_file(self.session_file_path)
                self.session_file_path = None
                
            self.logger.info("🗑️ Telegram adapter cleaned up")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def normalize_target(self, target: str) -> str:
        """Normalize Telegram target identifier."""
        target = target.strip()
        
        # Remove t.me/ prefix if present
        if target.startswith('https://t.me/'):
            target = target.replace('https://t.me/', '')
        elif target.startswith('t.me/'):
            target = target.replace('t.me/', '')
        
        # Keep @ prefix for Telegram
        if not target.startswith('@') and not target.isdigit():
            target = '@' + target
        
        return target 