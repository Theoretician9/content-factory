"""
Vault integration for multi-platform parsing service.

Handles authentication and retrieval of platform-specific secrets
including Telegram .session files, Instagram API tokens, etc.
"""

import os
import tempfile
import json
import logging
import requests
import time
from typing import Optional, Dict, Any
import hvac
from hvac.exceptions import VaultError

logger = logging.getLogger(__name__)


class VaultClient:
    """Client for HashiCorp Vault integration with AppRole authentication."""
    
    def __init__(self):
        # Use environment variables directly to avoid circular import
        self.vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8201')
        self.client = hvac.Client(url=self.vault_addr)
        self.vault_token = None
        self.token_expires_at = None  # Время истечения токена
        
        # AppRole Authentication
        self.role_id = os.getenv('VAULT_ROLE_ID')
        self.secret_id = os.getenv('VAULT_SECRET_ID')
        
        if self.role_id and self.secret_id:
            self._authenticate_with_approle()
        else:
            self.vault_token = os.getenv('VAULT_TOKEN')
            self.client.token = self.vault_token
    
    def _authenticate_with_approle(self):
        """Authenticate with Vault using AppRole."""
        try:
            auth_data = {"role_id": self.role_id, "secret_id": self.secret_id}
            response = self.client.auth.approle.login(**auth_data)
            
            self.vault_token = response["auth"]["client_token"]
            self.client.token = self.vault_token
            
            # Сохраняем время истечения токена
            lease_duration = response["auth"]["lease_duration"]
            self.token_expires_at = time.time() + lease_duration - 300  # Обновляем за 5 минут до истечения
            
            logger.info(f"✅ AppRole authentication successful. Token valid for {lease_duration} seconds")
        except Exception as e:
            logger.error(f"❌ AppRole authentication failed: {e}")
            self.vault_token = os.getenv('VAULT_TOKEN')
            self.client.token = self.vault_token
            self.token_expires_at = None
    
    def _is_token_valid(self) -> bool:
        """Проверка валидности токена."""
        if not self.vault_token:
            return False
        
        if self.token_expires_at is None:
            return True  # Для статических токенов
        
        return time.time() < self.token_expires_at
    
    def _refresh_token_if_needed(self):
        """Обновление токена при необходимости."""
        if not self._is_token_valid() and self.role_id and self.secret_id:
            logger.info("🔄 PARSING-SERVICE: Token expired or invalid, refreshing with AppRole...")
            self._authenticate_with_approle()
            logger.info("✅ PARSING-SERVICE: Token refreshed successfully")
    
    def get_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get secret from Vault KV v2 engine.
        
        Args:
            path: Secret path (e.g., 'jwt')
            
        Returns:
            Secret data or None if not found
        """
        try:
            # Проверяем и обновляем токен при необходимости
            self._refresh_token_if_needed()
            
            # Используем прямой HTTP запрос как в integration-service
            # для правильного обращения к KV engine с именем 'kv'
            url = f"{self.vault_addr}/v1/kv/data/{path}"
            headers = {"X-Vault-Token": self.vault_token}
            
            logger.debug(f"🔍 Getting secret from URL: {url}")
            
            response = requests.get(url, headers=headers)
            
            # Обработка ошибки 403 (токен истек)
            if response.status_code == 403:
                logger.warning("🔄 PARSING-SERVICE: Received 403, attempting to refresh token...")
                self._authenticate_with_approle()
                headers = {"X-Vault-Token": self.vault_token}
                response = requests.get(url, headers=headers)
                logger.info("✅ PARSING-SERVICE: Token refreshed, retrying request")
            
            response.raise_for_status()
            
            return response.json()["data"]["data"]
            
        except Exception as e:
            logger.error(f"❌ Failed to get secret from {path}: {e}")
            return None
    
    def get_platform_api_keys(self, platform: str) -> Optional[Dict[str, str]]:
        """
        Get API keys for specific platform.
        
        Args:
            platform: Platform name (telegram, instagram, whatsapp)
            
        Returns:
            Dictionary with API keys or None
        """
        if platform == "telegram":
            # For Telegram, get API keys from integration-service secret (where they actually are)
            secret_data = self.get_secret("integration-service")
            if secret_data:
                return {
                    'api_id': secret_data.get('telegram_api_id'),
                    'api_hash': secret_data.get('telegram_api_hash')
                }
        else:
            # For other platforms, use the standard path
            path = f"integrations/{platform}"
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