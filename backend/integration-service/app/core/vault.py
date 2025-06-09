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
            
            # Ждем инициализации Vault
            self._wait_for_vault()
            
            logger.info("Vault client initialized successfully")
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

    def _initialize_vault(self):
        """Инициализируем Vault если он еще не инициализирован"""
        try:
            # Проверяем статус инициализации
            if not self.client.sys.is_initialized():
                logger.info("Initializing Vault...")
                # Инициализируем с 1 ключом (для dev/test среды)
                result = self.client.sys.initialize(secret_shares=1, secret_threshold=1)
                
                # Сохраняем root token
                self.vault_token = result['root_token']
                self.client.token = self.vault_token
                
                # Распечатываем Vault с помощью unseal key
                unseal_key = result['keys'][0]
                self.client.sys.submit_unseal_key(unseal_key)
                
                logger.info("Vault initialized and unsealed successfully")
            elif self.client.sys.is_sealed():
                logger.warning("Vault is sealed but already initialized")
                # В production здесь нужно будет ввести unseal ключи
                # Для dev/test среды можно попробовать автоматически
            else:
                logger.info("Vault is already initialized and unsealed")
                
        except Exception as e:
            logger.error(f"Error initializing Vault: {e}")

    def _ensure_secrets_mount(self):
        """Проверяет существование секретов (без системных операций)"""
        if not self.client:
            return
            
        try:
            # Просто проверяем существование секрета Telegram без системных вызовов
            try:
                secret = self.get_secret('integrations/telegram')
                logger.info(f"Telegram credentials found in Vault: API ID {secret.get('api_id')}")
            except Exception as e:
                logger.info(f"Telegram credentials not found in Vault: {e}")
                
                # Получаем реальные Telegram API credentials из переменных окружения
                telegram_api_id = os.getenv('TELEGRAM_API_ID')
                telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
                
                if telegram_api_id and telegram_api_hash:
                    # Создаем секрет в Vault
                    self.put_secret('integrations/telegram', {
                        'api_id': telegram_api_id,
                        'api_hash': telegram_api_hash,
                        'webhook_url': '',
                        'proxy': ''
                    })
                    logger.info(f"Initialized Telegram credentials in Vault with api_id: {telegram_api_id}")
                else:
                    logger.warning("TELEGRAM_API_ID and TELEGRAM_API_HASH not found in environment variables")
                
        except Exception as e:
            logger.error(f"Error in _ensure_secrets_mount: {e}")

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
                mount_point='kv'
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
            response = self.client.secrets.kv.v2.list_secrets(path='integrations', mount_point='kv')
            return response['data']['keys']
        except:
            # Возвращаем пустой список при ошибке
            return [] 