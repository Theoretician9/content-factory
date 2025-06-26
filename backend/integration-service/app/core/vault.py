import os
import requests
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class IntegrationVaultClient:
    def __init__(self, vault_addr: str = None, vault_token: str = None, role_id: str = None, secret_id: str = None):
        self.vault_addr = vault_addr or os.getenv('VAULT_ADDR', 'http://vault:8201')
        self.vault_token = None
        self.token_expires_at = None  # Время истечения токена
        
        # Поддержка AppRole Authentication
        self.role_id = role_id or os.getenv('VAULT_ROLE_ID')
        self.secret_id = secret_id or os.getenv('VAULT_SECRET_ID')
        
        # Fallback на токенную аутентификацию
        if not self.role_id or not self.secret_id:
            self.vault_token = vault_token or os.getenv('VAULT_TOKEN')
            logger.info("DEBUG VaultClient.__init__: Using token authentication")
            logger.info(f"DEBUG VaultClient.__init__: vault_addr = {self.vault_addr}")
            logger.info(f"DEBUG VaultClient.__init__: vault_token = {self.vault_token[:20]}..." if self.vault_token else "No token")
            if not self.vault_token:
                raise ValueError("Vault token is required when AppRole credentials are not provided")
        else:
            logger.info("DEBUG VaultClient.__init__: Using AppRole authentication")
            logger.info(f"DEBUG VaultClient.__init__: vault_addr = {self.vault_addr}")
            logger.info(f"DEBUG VaultClient.__init__: role_id = {self.role_id}")
            logger.info(f"DEBUG VaultClient.__init__: secret_id = {self.secret_id[:10]}...")
            self._authenticate_with_approle()
            
        # Ждем пока Vault станет доступен
        self._wait_for_vault()

    def _authenticate_with_approle(self):
        """Аутентификация через AppRole и получение токена"""
        try:
            auth_data = {
                "role_id": self.role_id,
                "secret_id": self.secret_id
            }
            
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
            
            logger.info("DEBUG VaultClient._authenticate_with_approle: Successfully authenticated via AppRole")
            logger.info(f"DEBUG VaultClient._authenticate_with_approle: token = {self.vault_token[:20]}...")
            logger.info(f"DEBUG VaultClient._authenticate_with_approle: Token valid for {lease_duration} seconds")
            
        except Exception as e:
            logger.error(f"ERROR VaultClient._authenticate_with_approle: Failed to authenticate: {e}")
            raise ValueError(f"AppRole authentication failed: {e}")

    def _wait_for_vault(self, max_attempts=30, delay=2):
        """Ждем пока Vault станет доступен"""
        for attempt in range(max_attempts):
            try:
                response = requests.get(
                    f"{self.vault_addr}/v1/sys/health",
                    headers={"X-Vault-Token": self.vault_token}
                )
                response.raise_for_status()
                logger.info(f"Vault is available, status: {response}")
                return
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.info(f"Waiting for Vault... attempt {attempt + 1}/{max_attempts}")
                    time.sleep(delay)
                else:
                    logger.error(f"Vault is not available after {max_attempts} attempts: {e}")
                    raise

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
            logger.info("🔄 Token expired, refreshing with AppRole...")
            self._authenticate_with_approle()

    def get_secret(self, path: str) -> Dict[str, Any]:
        """
        Получить секрет из Vault
        :param path: путь к секрету (например, 'integration-service')
        :return: данные секрета
        """
        # Проверяем и обновляем токен при необходимости
        self._refresh_token_if_needed()
        
        # Автоматически добавляем kv/data/ префикс для KV v2 engine
        full_path = f"kv/data/{path}"
        url = f"{self.vault_addr}/v1/{full_path}"
        headers = {"X-Vault-Token": self.vault_token}
        
        logger.debug(f"DEBUG VaultClient.get_secret: path = {path}")
        logger.debug(f"DEBUG VaultClient.get_secret: full_path = {full_path}")
        logger.debug(f"DEBUG VaultClient.get_secret: self.vault_addr = {self.vault_addr}")
        logger.debug(f"DEBUG VaultClient.get_secret: constructed URL = {url}")
        logger.debug(f"DEBUG VaultClient.get_secret: headers = {{'X-Vault-Token': '{self.vault_token[:20]}...'}}")
        
        try:
            response = requests.get(url, headers=headers)
            logger.debug(f"DEBUG VaultClient.get_secret: response.status_code = {response.status_code}")
            logger.debug(f"DEBUG VaultClient.get_secret: response.url = {response.url}")
            
            # Обработка ошибки 403 (токен истек)
            if response.status_code == 403:
                logger.warning("🔄 Received 403, attempting to refresh token...")
                self._authenticate_with_approle()
                headers = {"X-Vault-Token": self.vault_token}
                response = requests.get(url, headers=headers)
                logger.debug(f"DEBUG VaultClient.get_secret: retry response.status_code = {response.status_code}")
            
            response.raise_for_status()
            return response.json()["data"]["data"]
        except Exception as e:
            logger.error(f"Error getting secret {path}: {e}")
            raise

    def put_secret(self, path: str, data: Dict[str, Any]) -> None:
        """
        Сохранить секрет в Vault
        :param path: путь к секрету
        :param data: данные для сохранения
        """
        full_path = f"kv/data/{path}"
        response = requests.post(
            f"{self.vault_addr}/v1/{full_path}",
            headers={"X-Vault-Token": self.vault_token},
            json={"data": data}
        )
        response.raise_for_status()
        logger.info(f"Successfully saved secret to Vault: {path}")

    def delete_secret(self, path: str) -> None:
        """Удалить секрет из Vault"""
        full_path = f"kv/metadata/{path}"
        response = requests.delete(
            f"{self.vault_addr}/v1/{full_path}",
            headers={"X-Vault-Token": self.vault_token}
        )
        response.raise_for_status()

    def get_integration_credentials(self, platform: str) -> Dict[str, Any]:
        try:
            return self.get_secret(f'integrations/{platform}')
        except Exception as e:
            logger.error(f"Error getting credentials for {platform}: {e}")
            return {}

    def update_integration_credentials(self, platform: str, credentials: Dict[str, Any]) -> None:
        self.put_secret(f'integrations/{platform}', credentials)

    def delete_integration_credentials(self, platform: str) -> None:
        self.delete_secret(f'integrations/{platform}')

    def list_integrations(self) -> list:
        try:
            response = requests.get(
                f"{self.vault_addr}/v1/kv/metadata/integrations",
                headers={"X-Vault-Token": self.vault_token}
            )
            response.raise_for_status()
            return response.json()["data"]["keys"]
        except:
            # Возвращаем пустой список при ошибке
            return []


# Global vault client instance
_vault_client = None


def get_vault_client() -> IntegrationVaultClient:
    """Get global Integration Vault client instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = IntegrationVaultClient()
    return _vault_client 