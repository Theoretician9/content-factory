from typing import Dict, Any
import os
import hvac
import logging
import time

logger = logging.getLogger(__name__)

class IntegrationVaultClient:
    def __init__(self):
        # Используем правильный адрес Vault из docker-compose
        self.vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8201')
        self.vault_token = os.getenv('VAULT_TOKEN', 'root')
        try:
            self.client = hvac.Client(url=self.vault_addr, token=self.vault_token)
            self._wait_for_vault()
        except Exception as e:
            logger.warning(f"Could not initialize Vault client: {e}")
            self.client = None

    def _wait_for_vault(self, max_attempts=30, delay=2):
        """Ждем пока Vault станет доступен"""
        for attempt in range(max_attempts):
            try:
                status = self.client.sys.read_health_status()
                logger.info(f"Vault is available, status: {status}")
                return
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.info(f"Waiting for Vault... attempt {attempt + 1}/{max_attempts}")
                    time.sleep(delay)
                else:
                    logger.error(f"Vault is not available after {max_attempts} attempts: {e}")
                    raise

    def get_secret(self, path: str) -> Dict[str, Any]:
        """Получить секрет из Vault"""
        if not self.client:
            raise Exception("Vault client not initialized")
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point='kv'
            )
            if not response or 'data' not in response or 'data' not in response['data']:
                raise Exception(f"Invalid response format from Vault for path {path}")
            return response['data']['data']
        except Exception as e:
            logger.error(f"Error getting secret {path}: {e}")
            raise

    def put_secret(self, path: str, data: Dict[str, Any]) -> None:
        """Сохранить секрет в Vault"""
        if not self.client:
            raise Exception("Vault client not initialized")
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point='kv'
            )
            logger.info(f"Successfully saved secret to Vault: {path}")
        except Exception as e:
            logger.error(f"Error putting secret {path}: {e}")
            raise

    def delete_secret(self, path: str) -> None:
        """Удалить секрет из Vault"""
        if not self.client:
            raise Exception("Vault client not initialized")
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point='kv'
            )
        except Exception as e:
            logger.error(f"Error deleting secret {path}: {e}")
            raise

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
        if not self.client:
            return []
        
        try:
            response = self.client.secrets.kv.v2.list_secrets(path='integrations', mount_point='kv')
            return response['data']['keys']
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