"""
Vault integration for Invite Service.

Handles authentication and retrieval of secrets including JWT keys
and platform-specific credentials for mass invitations.
"""

import os
import logging
import requests
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class InviteVaultClient:
    """Client for HashiCorp Vault integration with AppRole authentication for Invite Service."""
    
    def __init__(self):
        # Use environment variables directly to avoid circular import
        self.vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8201')
        self.vault_token = None
        self.token_expires_at = None  # Время истечения токена
        
        # AppRole Authentication
        self.role_id = os.getenv('VAULT_ROLE_ID')
        self.secret_id = os.getenv('VAULT_SECRET_ID')
        
        if self.role_id and self.secret_id:
            logger.info("🔐 INVITE-SERVICE: Initializing with AppRole authentication")
            self._authenticate_with_approle()
        else:
            logger.info("🔐 INVITE-SERVICE: Falling back to token authentication")
            self.vault_token = os.getenv('VAULT_TOKEN')
            self.token_expires_at = None  # Статические токены не истекают
            
            if not self.vault_token:
                logger.error("❌ INVITE-SERVICE: No Vault token or AppRole credentials provided")
                raise ValueError("Vault token or AppRole credentials are required")
    
    def _authenticate_with_approle(self):
        """Authenticate with Vault using AppRole."""
        try:
            auth_data = {"role_id": self.role_id, "secret_id": self.secret_id}
            response = requests.post(
                f"{self.vault_addr}/v1/auth/approle/login",
                json=auth_data
            )
            response.raise_for_status()
            
            auth_result = response.json()
            self.vault_token = auth_result["auth"]["client_token"]
            
            # Сохраняем время истечения токена
            lease_duration = auth_result["auth"]["lease_duration"]
            self.token_expires_at = time.time() + lease_duration - 300  # Обновляем за 5 минут до истечения
            
            logger.info(f"✅ INVITE-SERVICE: AppRole authentication successful. Token valid for {lease_duration} seconds")
            
        except Exception as e:
            logger.error(f"❌ INVITE-SERVICE: AppRole authentication failed: {e}")
            # Fallback на токенную аутентификацию
            self.vault_token = os.getenv('VAULT_TOKEN')
            self.token_expires_at = None
            if not self.vault_token:
                raise ValueError(f"AppRole authentication failed and no fallback token: {e}")
    
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
            logger.info("🔄 INVITE-SERVICE: Token expired or invalid, refreshing with AppRole...")
            self._authenticate_with_approle()
            logger.info("✅ INVITE-SERVICE: Token refreshed successfully")
    
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
            
            # Используем правильный путь для KV v2 engine
            url = f"{self.vault_addr}/v1/kv/data/{path}"
            headers = {"X-Vault-Token": self.vault_token}
            
            logger.debug(f"🔍 INVITE-SERVICE: Getting secret from URL: {url}")
            
            response = requests.get(url, headers=headers)
            
            # Обработка ошибки 403 (токен истек)
            if response.status_code == 403:
                logger.warning("🔄 INVITE-SERVICE: Received 403, attempting to refresh token...")
                self._authenticate_with_approle()
                headers = {"X-Vault-Token": self.vault_token}
                response = requests.get(url, headers=headers)
                logger.info("✅ INVITE-SERVICE: Token refreshed, retrying request")
            
            response.raise_for_status()
            
            return response.json()["data"]["data"]
            
        except Exception as e:
            logger.error(f"❌ INVITE-SERVICE: Failed to get secret from {path}: {e}")
            return None
    
    def put_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """
        Store secret in Vault KV v2 engine.
        
        Args:
            path: Secret path
            data: Data to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Проверяем и обновляем токен при необходимости
            self._refresh_token_if_needed()
            
            url = f"{self.vault_addr}/v1/kv/data/{path}"
            headers = {"X-Vault-Token": self.vault_token}
            
            response = requests.post(url, headers=headers, json={"data": data})
            
            # Обработка ошибки 403 (токен истек)
            if response.status_code == 403:
                logger.warning("🔄 INVITE-SERVICE: Received 403, attempting to refresh token...")
                self._authenticate_with_approle()
                headers = {"X-Vault-Token": self.vault_token}
                response = requests.post(url, headers=headers, json={"data": data})
                logger.info("✅ INVITE-SERVICE: Token refreshed, retrying request")
            
            response.raise_for_status()
            logger.info(f"✅ INVITE-SERVICE: Successfully stored secret at {path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ INVITE-SERVICE: Failed to store secret at {path}: {e}")
            return False
    
    def get_platform_credentials(self, platform: str) -> Optional[Dict[str, Any]]:
        """
        Get platform-specific credentials for invitations.
        
        Args:
            platform: Platform name (telegram, instagram, whatsapp)
            
        Returns:
            Dictionary with platform credentials or None
        """
        if platform == "telegram":
            # For Telegram, get API keys from integration-service secret
            secret_data = self.get_secret("integration-service")
            if secret_data:
                return {
                    'api_id': secret_data.get('telegram_api_id'),
                    'api_hash': secret_data.get('telegram_api_hash')
                }
        else:
            # For other platforms, use platform-specific path
            path = f"invite-service/{platform}"
            return self.get_secret(path)
        
        return None
    
    def get_invitation_templates(self, platform: str) -> Optional[Dict[str, Any]]:
        """
        Get invitation message templates for platform.
        
        Args:
            platform: Platform name
            
        Returns:
            Dictionary with message templates or None
        """
        path = f"invite-service/templates/{platform}"
        return self.get_secret(path)
    
    def store_invitation_templates(self, platform: str, templates: Dict[str, Any]) -> bool:
        """
        Store invitation message templates for platform.
        
        Args:
            platform: Platform name
            templates: Message templates data
            
        Returns:
            True if successful, False otherwise
        """
        path = f"invite-service/templates/{platform}"
        return self.put_secret(path, templates)
    
    def health_check(self) -> bool:
        """
        Check Vault connectivity and authentication.
        
        Returns:
            True if Vault is accessible and authenticated
        """
        try:
            # Проверяем и обновляем токен при необходимости
            self._refresh_token_if_needed()
            
            # Проверяем доступность Vault
            response = requests.get(
                f"{self.vault_addr}/v1/sys/health",
                headers={"X-Vault-Token": self.vault_token}
            )
            
            if response.status_code in [200, 429]:  # 200 = healthy, 429 = standby
                logger.info("✅ INVITE-SERVICE: Vault health check passed")
                return True
            else:
                logger.error(f"❌ INVITE-SERVICE: Vault health check failed with status {response.status_code}")
                return False
            
        except Exception as e:
            logger.error(f"❌ INVITE-SERVICE: Vault health check failed: {e}")
            return False


# Global Vault client instance
_vault_client: Optional[InviteVaultClient] = None


def get_vault_client() -> InviteVaultClient:
    """Get global Vault client instance for Invite Service."""
    global _vault_client
    if _vault_client is None:
        _vault_client = InviteVaultClient()
    return _vault_client 