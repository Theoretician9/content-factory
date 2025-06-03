from typing import Dict, Any
import sys
import os

# Добавляем путь к общему модулю
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../common'))
from vault_client import VaultClient

class IntegrationVaultClient(VaultClient):
    def __init__(self):
        # Используем правильный адрес Vault из docker-compose
        vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8201')
        vault_token = os.getenv('VAULT_TOKEN', 'root')
        super().__init__(vault_addr, vault_token)
        self._ensure_secrets_mount()

    def _ensure_secrets_mount(self):
        """Проверяет и создает необходимые пути для секретов"""
        try:
            # Пытаемся получить существующие секреты
            self.get_secret('secret/data/integrations/telegram')
        except:
            # Создаем базовую структуру для интеграций
            try:
                self.put_secret('secret/data/integrations/telegram', {
                    'api_id': '29948572',  # Тестовый API ID (замените на реальный)
                    'api_hash': 'your_api_hash_here',  # Замените на реальный API Hash
                    'webhook_url': '',
                    'proxy': ''
                })
                self.put_secret('secret/data/integrations/vk', {
                    'api_key': '',
                    'group_token': '',
                    'proxy': ''
                })
                self.put_secret('secret/data/integrations/whatsapp', {
                    'api_key': '',
                    'phone_number': '',
                    'proxy': ''
                })
            except Exception as e:
                # Логируем ошибку, но не падаем
                print(f"Warning: Could not initialize Vault secrets: {e}")

    def get_integration_credentials(self, platform: str) -> Dict[str, Any]:
        """
        Получает учетные данные для конкретной платформы
        :param platform: название платформы (telegram, vk, whatsapp)
        :return: словарь с учетными данными
        """
        try:
            return self.get_secret(f'secret/data/integrations/{platform}')
        except Exception as e:
            print(f"Error getting credentials for {platform}: {e}")
            # Возвращаем пустые данные при ошибке
            return {}

    def update_integration_credentials(self, platform: str, credentials: Dict[str, Any]) -> None:
        """
        Обновляет учетные данные для платформы
        :param platform: название платформы
        :param credentials: новые учетные данные
        """
        self.put_secret(f'secret/data/integrations/{platform}', credentials)

    def delete_integration_credentials(self, platform: str) -> None:
        """
        Удаляет учетные данные платформы
        :param platform: название платформы
        """
        self.delete_secret(f'secret/data/integrations/{platform}')

    def list_integrations(self) -> list:
        """
        Получает список доступных интеграций
        :return: список платформ
        """
        try:
            return self.list_secrets('secret/metadata/integrations')
        except:
            # Возвращаем пустой список при ошибке
            return [] 