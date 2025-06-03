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
            # Пытаемся получить существующие секреты
            self.get_secret('integrations/telegram')
        except:
            # Создаем базовую структуру для интеграций
            try:
                # Получаем реальные Telegram API credentials из переменных окружения
                telegram_api_id = os.getenv('TELEGRAM_API_ID', '23699038')
                telegram_api_hash = os.getenv('TELEGRAM_API_HASH', '055c48aee9080db331639a87f85617b4')
                
                self.put_secret('integrations/telegram', {
                    'api_id': telegram_api_id,
                    'api_hash': telegram_api_hash,
                    'webhook_url': '',
                    'proxy': ''
                })
                logger.info(f"Initialized Telegram credentials in Vault with api_id: {telegram_api_id}")
                
                self.put_secret('integrations/vk', {
                    'api_key': '',
                    'group_token': '',
                    'proxy': ''
                })
                self.put_secret('integrations/whatsapp', {
                    'api_key': '',
                    'phone_number': '',
                    'proxy': ''
                })
            except Exception as e:
                # Логируем ошибку, но не падаем
                logger.warning(f"Could not initialize Vault secrets: {e}")

    def get_secret(self, path: str) -> Dict[str, Any]:
        """Получить секрет из Vault"""
        if not self.client:
            raise Exception("Vault client not initialized")
        
        try:
            response = self.client.secrets.kv.v2.read_secret_version(path=path)
            return response['data']['data']
        except Exception as e:
            logger.error(f"Error getting secret {path}: {e}, on get {self.vault_addr}/v1/secret/data/{path}")
            raise

    def put_secret(self, path: str, data: Dict[str, Any]) -> None:
        """Сохранить секрет в Vault"""
        if not self.client:
            raise Exception("Vault client not initialized")
        
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data
            )
        except Exception as e:
            logger.error(f"Error putting secret {path}: {e}")
            raise

    def delete_secret(self, path: str) -> None:
        """Удалить секрет из Vault"""
        if not self.client:
            raise Exception("Vault client not initialized")
        
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path
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