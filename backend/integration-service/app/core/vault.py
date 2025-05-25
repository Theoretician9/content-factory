from typing import Dict, Any
import sys
import os

# Добавляем путь к общему модулю
sys.path.append(os.path.join(os.path.dirname(__file__), '../../common'))
from vault_client import VaultClient

class IntegrationVaultClient(VaultClient):
    def __init__(self):
        super().__init__()
        self._ensure_secrets_mount()

    def _ensure_secrets_mount(self):
        """Проверяет и создает необходимые пути для секретов"""
        try:
            self.list_secrets('secret/data/integrations')
        except:
            # Создаем базовую структуру для интеграций
            self.put_secret('secret/data/integrations/telegram', {
                'api_key': '',
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

    def get_integration_credentials(self, platform: str) -> Dict[str, Any]:
        """
        Получает учетные данные для конкретной платформы
        :param platform: название платформы (telegram, vk, whatsapp)
        :return: словарь с учетными данными
        """
        return self.get_secret(f'secret/data/integrations/{platform}')

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
        return self.list_secrets('secret/data/integrations') 