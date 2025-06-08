import os
import requests
from typing import Dict, Any, Optional

class VaultClient:
    def __init__(self, vault_addr: str = None, vault_token: str = None):
        self.vault_addr = vault_addr or os.getenv('VAULT_ADDR', 'http://vault:8200')
        self.vault_token = vault_token or os.getenv('VAULT_TOKEN')
        if not self.vault_token:
            raise ValueError("Vault token is required")

    def get_secret(self, path: str) -> Dict[str, Any]:
        """
        Получить секрет из Vault
        :param path: путь к секрету (например, 'secret/data/db')
        :return: данные секрета
        """
        response = requests.get(
            f"{self.vault_addr}/v1/{path}",
            headers={"X-Vault-Token": self.vault_token}
        )
        response.raise_for_status()
        return response.json()["data"]["data"]

    def put_secret(self, path: str, data: Dict[str, Any]) -> None:
        """
        Сохранить секрет в Vault
        :param path: путь к секрету
        :param data: данные для сохранения
        """
        response = requests.post(
            f"{self.vault_addr}/v1/{path}",
            headers={"X-Vault-Token": self.vault_token},
            json={"data": data}
        )
        response.raise_for_status()

    def delete_secret(self, path: str) -> None:
        """
        Удалить секрет из Vault
        :param path: путь к секрету
        """
        response = requests.delete(
            f"{self.vault_addr}/v1/{path}",
            headers={"X-Vault-Token": self.vault_token}
        )
        response.raise_for_status()

    def list_secrets(self, path: str) -> list:
        """
        Получить список секретов
        :param path: путь к директории с секретами
        :return: список секретов
        """
        response = requests.get(
            f"{self.vault_addr}/v1/{path}",
            headers={"X-Vault-Token": self.vault_token}
        )
        response.raise_for_status()
        return response.json()["data"]["keys"] 