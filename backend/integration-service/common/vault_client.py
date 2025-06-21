import os
import requests
from typing import Dict, Any, Optional

class VaultClient:
    def __init__(self, vault_addr: str = None, vault_token: str = None, role_id: str = None, secret_id: str = None):
        self.vault_addr = vault_addr or os.getenv('VAULT_ADDR', 'http://vault:8201')
        self.vault_token = None
        
        # Поддержка AppRole Authentication
        self.role_id = role_id or os.getenv('VAULT_ROLE_ID')
        self.secret_id = secret_id or os.getenv('VAULT_SECRET_ID')
        
        # Fallback на токенную аутентификацию
        if not self.role_id or not self.secret_id:
            self.vault_token = vault_token or os.getenv('VAULT_TOKEN')
            print(f"DEBUG VaultClient.__init__: Using token authentication")
            print(f"DEBUG VaultClient.__init__: vault_addr = {self.vault_addr}")
            print(f"DEBUG VaultClient.__init__: vault_token = {self.vault_token[:20]}..." if self.vault_token else "No token")
            if not self.vault_token:
                raise ValueError("Vault token is required when AppRole credentials are not provided")
        else:
            print(f"DEBUG VaultClient.__init__: Using AppRole authentication")
            print(f"DEBUG VaultClient.__init__: vault_addr = {self.vault_addr}")
            print(f"DEBUG VaultClient.__init__: role_id = {self.role_id}")
            print(f"DEBUG VaultClient.__init__: secret_id = {self.secret_id[:10]}...")
            self._authenticate_with_approle()

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
            print(f"DEBUG VaultClient._authenticate_with_approle: Successfully authenticated via AppRole")
            print(f"DEBUG VaultClient._authenticate_with_approle: token = {self.vault_token[:20]}...")
            
        except Exception as e:
            print(f"ERROR VaultClient._authenticate_with_approle: Failed to authenticate: {e}")
            raise ValueError(f"AppRole authentication failed: {e}")

    def get_secret(self, path: str) -> Dict[str, Any]:
        """
        Получить секрет из Vault
        :param path: путь к секрету (например, 'secret/data/db')
        :return: данные секрета
        """
        url = f"{self.vault_addr}/v1/{path}"
        headers = {"X-Vault-Token": self.vault_token}
        
        print(f"DEBUG VaultClient.get_secret: path = {path}")
        print(f"DEBUG VaultClient.get_secret: self.vault_addr = {self.vault_addr}")
        print(f"DEBUG VaultClient.get_secret: constructed URL = {url}")
        print(f"DEBUG VaultClient.get_secret: headers = {{'X-Vault-Token': '{self.vault_token[:20]}...'}}")
        
        try:
            response = requests.get(url, headers=headers)
            print(f"DEBUG VaultClient.get_secret: response.status_code = {response.status_code}")
            print(f"DEBUG VaultClient.get_secret: response.url = {response.url}")
            response.raise_for_status()
            return response.json()["data"]["data"]
        except Exception as e:
            print(f"DEBUG VaultClient.get_secret: Exception occurred = {e}")
            print(f"DEBUG VaultClient.get_secret: Exception type = {type(e)}")
            raise

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