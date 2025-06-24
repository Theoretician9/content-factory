"""
Vault integration for multi-platform parsing service.

Handles authentication and retrieval of platform-specific secrets
including Telegram .session files, Instagram API tokens, etc.
"""

import os
import tempfile
import json
import logging
from typing import Optional, Dict, Any
import hvac
from hvac.exceptions import VaultError
from enum import Enum

logger = logging.getLogger(__name__)


class Platform(str, Enum):
    """Supported social media platforms."""
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class VaultClient:
    """Client for HashiCorp Vault integration with AppRole authentication."""
    
    def __init__(self):
        # Use environment variables directly to avoid circular import
        self.vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8201')
        self.client = hvac.Client(url=self.vault_addr)
        self.vault_token = None
        
        # AppRole Authentication
        self.role_id = os.getenv('VAULT_ROLE_ID')
        self.secret_id = os.getenv('VAULT_SECRET_ID')
        
        if self.role_id and self.secret_id:
            self._authenticate_with_approle()
        else:
            self.vault_token = os.getenv('VAULT_TOKEN')
            self.client.token = self.vault_token
    
    def _authenticate_with_approle(self):
        """Authenticate with Vault using AppRole."""
        try:
            auth_data = {"role_id": self.role_id, "secret_id": self.secret_id}
            response = self.client.auth.approle.login(**auth_data)
            self.vault_token = response["auth"]["client_token"]
            self.client.token = self.vault_token
            logger.info("✅ AppRole authentication successful")
        except Exception as e:
            logger.error(f"❌ AppRole authentication failed: {e}")
            self.vault_token = os.getenv('VAULT_TOKEN')
            self.client.token = self.vault_token

    def get_secret(self, secret_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve a secret from Vault."""
        try:
            response = self.client.read(secret_path)
            if response:
                return response["data"]
            else:
                logger.warning(f"Secret '{secret_path}' not found in Vault")
                return None
        except VaultError as e:
            logger.error(f"❌ Error retrieving secret from Vault: {e}")
            return None

    def get_all_secrets(self) -> Dict[str, Dict[str, Any]]:
        """Retrieve all secrets from Vault."""
        try:
            response = self.client.list("/")
            if response:
                secrets = {}
                for item in response["data"]["keys"]:
                    secret_path = item.split("/")[-1]
                    secrets[secret_path] = self.get_secret(item)
                return secrets
            else:
                logger.warning("No secrets found in Vault")
                return {}
        except VaultError as e:
            logger.error(f"❌ Error retrieving all secrets from Vault: {e}")
            return {}

    def store_secret(self, secret_path: str, secret_data: Dict[str, Any]) -> bool:
        """Store a secret in Vault."""
        try:
            self.client.write(secret_path, **secret_data)
            logger.info(f"✅ Secret stored successfully at '{secret_path}'")
            return True
        except VaultError as e:
            logger.error(f"❌ Error storing secret in Vault: {e}")
            return False

    def delete_secret(self, secret_path: str) -> bool:
        """Delete a secret from Vault."""
        try:
            self.client.delete(secret_path)
            logger.info(f"✅ Secret deleted successfully from '{secret_path}'")
            return True
        except VaultError as e:
            logger.error(f"❌ Error deleting secret from Vault: {e}")
            return False

    def list_secrets(self) -> List[str]:
        """List all secret paths in Vault."""
        try:
            response = self.client.list("/")
            if response:
                return response["data"]["keys"]
            else:
                logger.warning("No secrets found in Vault")
                return []
        except VaultError as e:
            logger.error(f"❌ Error listing secrets in Vault: {e}")
            return [] 