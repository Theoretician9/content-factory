import os
import requests
import time
from typing import Dict, Any, Optional
from requests.exceptions import RequestException

class VaultClient:
    def __init__(self, vault_addr: str = None, vault_token: str = None, max_retries: int = 5, retry_delay: int = 2):
        self.vault_addr = vault_addr or os.getenv('VAULT_ADDR', 'http://vault:8200')
        self.vault_token = vault_token or os.getenv('VAULT_TOKEN')
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        if not self.vault_token:
            raise ValueError("Vault token is required")

    def _make_request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Выполнить запрос к Vault с повторными попытками
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method,
                    f"{self.vault_addr}/v1/{path}",
                    headers={"X-Vault-Token": self.vault_token},
                    **kwargs
                )
                response.raise_for_status()
                return response
            except RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay)
                continue

    def get_secret(self, path: str) -> Dict[str, Any]:
        """
        Получить секрет из Vault
        :param path: путь к секрету (например, 'secret/data/db')
        :return: данные секрета
        """
        response = self._make_request('GET', path)
        return response.json()["data"]["data"]

    def put_secret(self, path: str, data: Dict[str, Any]) -> None:
        """
        Сохранить секрет в Vault
        :param path: путь к секрету
        :param data: данные для сохранения
        """
        self._make_request('POST', path, json={"data": data})

    def delete_secret(self, path: str) -> None:
        """
        Удалить секрет из Vault
        :param path: путь к секрету
        """
        self._make_request('DELETE', path)

    def list_secrets(self, path: str) -> list:
        """
        Получить список секретов
        :param path: путь к директории с секретами
        :return: список секретов
        """
        response = self._make_request('GET', path)
        return response.json()["data"]["keys"] 