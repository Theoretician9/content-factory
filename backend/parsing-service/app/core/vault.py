"""
Vault integration for multi-platform parsing service.

Handles authentication and retrieval of platform-specific secrets
including Telegram .session files, Instagram API tokens, etc.
"""

import os
import tempfile
import json
import logging
from typing import Optional, Dict, Any
import hvac
from hvac.exceptions import VaultError

from .config import settings, Platform

logger = logging.getLogger(__name__)


class VaultClient:
    """Client for HashiCorp Vault integration with AppRole authentication."""
    
    def __init__(self):
        self.vault_addr = settings.VAULT_ADDR
        self.client = hvac.Client(url=self.vault_addr)
        self.vault_token = None
        
        # AppRole Authentication
        self.role_id = settings.VAULT_ROLE_ID
        self.secret_id = settings.VAULT_SECRET_ID
        
        if self.role_id and self.secret_id:
            self._authenticate_with_approle()
        else:
            self.vault_token = settings.VAULT_TOKEN
            self.client.token = self.vault_token
    
    def _authenticate_with_approle(self):
        """Authenticate with Vault using AppRole."""
        try:
            auth_data = {"role_id": self.role_id, "secret_id": self.secret_id}
            response = self.client.auth.approle.login(**auth_data)
            self.vault_token = response["auth"]["client_token"]
            self.client.token = self.vault_token
            logger.info("✅ AppRole authentication successful")
        except Exception as e:
            logger.error(f"❌ AppRole authentication failed: {e}")
            self.vault_token = settings.VAULT_TOKEN
            self.client.token = self.vault_token
    
    def get_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get secret from Vault KV v2 engine.
        
        Args:
            path: Secret path (e.g., 'integrations/telegram/api_keys')
            
        Returns:
            Secret data or None if not found
        """
        try:
            logger.debug(f"🔍 Getting secret from path: {path}")
            response = self.client.secrets.kv.v2.read_secret_version(path=path)
            return response['data']['data']
        except VaultError as e:
            logger.error(f"❌ Failed to get secret from {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error getting secret from {path}: {e}")
            return None
    
    def get_platform_api_keys(self, platform: Platform) -> Optional[Dict[str, str]]:
        """
        Get API keys for specific platform.
        
        Args:
            platform: Platform (telegram, instagram, whatsapp)
            
        Returns:
            Dictionary with API keys or None
        """
        if platform == Platform.TELEGRAM:
            # For Telegram, get API keys from integration-service secret (where they actually are)
            secret_data = self.get_secret("integration-service")
            if secret_data:
                return {
                    'api_id': secret_data.get('telegram_api_id'),
                    'api_hash': secret_data.get('telegram_api_hash')
                }
        else:
            # For other platforms, use the standard path
            path = f"integrations/{platform.value}"
            secret_data = self.get_secret(path)
            if secret_data:
                return {
                    'api_id': secret_data.get('api_id'),
                    'api_hash': secret_data.get('api_hash')
                }
        return None
    
    def get_telegram_session(self, session_id: str) -> Optional[bytes]:
        """
        Get Telegram .session file content from Vault.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session file content as bytes or None
        """
        try:
            path = f"integrations/telegram/sessions/{session_id}"
            secret_data = self.get_secret(path)
            
            if not secret_data or 'session_data' not in secret_data:
                logger.error(f"❌ No session data found for session_id: {session_id}")
                return None
            
            # Decode base64 session data
            import base64
            session_bytes = base64.b64decode(secret_data['session_data'])
            logger.info(f"✅ Retrieved Telegram session for {session_id}")
            return session_bytes
            
        except Exception as e:
            logger.error(f"❌ Failed to get Telegram session {session_id}: {e}")
            return None
    
    def create_temp_session_file(self, session_id: str) -> Optional[str]:
        """
        Create temporary .session file for Telegram client.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Path to temporary session file or None
        """
        try:
            session_data = self.get_telegram_session(session_id)
            if not session_data:
                return None
            
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.session', prefix=f'tg_{session_id}_')
            try:
                with os.fdopen(temp_fd, 'wb') as f:
                    f.write(session_data)
                logger.info(f"✅ Created temporary session file: {temp_path}")
                return temp_path
            except Exception as e:
                os.close(temp_fd)
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e
                
        except Exception as e:
            logger.error(f"❌ Failed to create temp session file for {session_id}: {e}")
            return None
    
    def cleanup_temp_file(self, file_path: str):
        """
        Safely remove temporary file.
        
        Args:
            file_path: Path to temporary file
        """
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"🗑️ Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.error(f"❌ Failed to cleanup temp file {file_path}: {e}")
    
    def get_instagram_token(self, account_id: str) -> Optional[str]:
        """
        Get Instagram API token for account (planned for Phase 2).
        
        Args:
            account_id: Instagram account identifier
            
        Returns:
            Access token or None
        """
        path = f"integrations/instagram/tokens/{account_id}"
        secret_data = self.get_secret(path)
        return secret_data.get('access_token') if secret_data else None
    
    def get_whatsapp_token(self, account_id: str) -> Optional[str]:
        """
        Get WhatsApp Business API token for account (planned for Phase 3).
        
        Args:
            account_id: WhatsApp account identifier
            
        Returns:
            Access token or None
        """
        path = f"integrations/whatsapp/tokens/{account_id}"
        secret_data = self.get_secret(path)
        return secret_data.get('access_token') if secret_data else None
    
    def health_check(self) -> bool:
        """
        Check Vault connectivity and authentication.
        
        Returns:
            True if Vault is accessible and authenticated
        """
        try:
            if not self.client.is_authenticated():
                logger.error("❌ Vault client is not authenticated")
                return False
            
            # Try to read a test path
            self.client.sys.read_health_status()
            logger.info("✅ Vault health check passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Vault health check failed: {e}")
            return False


# Global Vault client instance
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Get global Vault client instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client 