from typing import Dict, Any
import os
import hvac
import logging

logger = logging.getLogger(__name__)

class IntegrationVaultClient:
    def __init__(self):
        # Используем правильный адрес Vault из docker-compose
        self.vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8201')
        self.vault_token = os.getenv('VAULT_TOKEN', 'root')
        
        try:
            self.client = hvac.Client(url=self.vault_addr, token=self.vault_token)
            self._ensure_secrets_mount()
        except Exception as e:
            logger.warning(f"Could not initialize Vault client: {e}")
            self.client = None

    def _ensure_secrets_mount(self):
        """Проверяет и создает необходимые пути для секретов"""
        if not self.client:
            return
            
        try:
            # Проверяем, что KV v2 включен
            mounted_secrets = self.client.sys.list_mounted_secrets_engines()
            if 'kv/' not in mounted_secrets.get('data', {}):
                self.client.sys.enable_secrets_engine(
                    backend_type='kv',
                    options={'version': '2'},
                    path='kv'
                )
                logger.info("Enabled KV v2 secrets engine")
            
            # Проверяем существование секрета
            try:
                self.get_secret('integrations/telegram')
                logger.info("Telegram credentials found in Vault")
            except Exception as e:
                logger.info(f"Telegram credentials not found in Vault, initializing: {e}")
                # Получаем реальные Telegram API credentials из переменных окружения
                telegram_api_id = os.getenv('TELEGRAM_API_ID')
                telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
                
                if not telegram_api_id or not telegram_api_hash:
                    raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment")
                
                # Создаем секрет в Vault
                self.put_secret('integrations/telegram', {
                    'api_id': telegram_api_id,
                    'api_hash': telegram_api_hash,
                    'webhook_url': '',
                    'proxy': ''
                })
                logger.info(f"Initialized Telegram credentials in Vault with api_id: {telegram_api_id}")
                
        except Exception as e:
            logger.error(f"Error in _ensure_secrets_mount: {e}")
            raise

    def get_secret(self, path: str) -> Dict[str, Any]:
        """Получить секрет из Vault"""
        if not self.client:
            raise Exception("Vault client not initialized")
        
        try:
            # Используем правильный путь для KV v2
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
            # Используем правильный путь для KV v2
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
            # Используем правильный путь для KV v2
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point='kv'  # Явно указываем mount point
            )
        except Exception as e:
            logger.error(f"Error deleting secret {path}: {e}")
            raise

    def get_integration_credentials(self, platform: str) -> Dict[str, Any]:
        """
        Получает учетные данные для конкретной платформы
        :param platform: название платформы (telegram, vk, whatsapp)
        :return: словарь с учетными данными
        """
        try:
            return self.get_secret(f'integrations/{platform}')
        except Exception as e:
            logger.error(f"Error getting credentials for {platform}: {e}")
            # Возвращаем пустые данные при ошибке
            return {}

    def update_integration_credentials(self, platform: str, credentials: Dict[str, Any]) -> None:
        """
        Обновляет учетные данные для платформы
        :param platform: название платформы
        :param credentials: новые учетные данные
        """
        self.put_secret(f'integrations/{platform}', credentials)

    def delete_integration_credentials(self, platform: str) -> None:
        """
        Удаляет учетные данные платформы
        :param platform: название платформы
        """
        self.delete_secret(f'integrations/{platform}')

    def list_integrations(self) -> list:
        """
        Получает список доступных интеграций
        :return: список платформ
        """
        if not self.client:
            return []
        
        try:
            response = self.client.secrets.kv.v2.list_secrets(path='integrations')
            return response['data']['keys']
        except:
            # Возвращаем пустой список при ошибке
            return [] 