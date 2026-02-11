import logging
import os
import time
from typing import Any, Dict, Optional

import requests


logger = logging.getLogger(__name__)


class ServiceVaultClient:
    """
    Универсальный Vault‑клиент для evolution-agent.

    Использует AppRole, при отсутствии role_id/secret_id падает обратно на VAULT_TOKEN.
    Работает с KV v2 (`kv/data/<path>`), как описано в PROJECT.
    """

    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
        role_id: Optional[str] = None,
        secret_id: Optional[str] = None,
    ):
        self.vault_addr = vault_addr or os.getenv("VAULT_ADDR", "http://vault:8201")
        self.vault_token: Optional[str] = None
        self.token_expires_at: Optional[float] = None

        # AppRole
        self.role_id = role_id or os.getenv("VAULT_ROLE_ID")
        self.secret_id = secret_id or os.getenv("VAULT_SECRET_ID")

        if self.role_id and self.secret_id:
            logger.info("🔐 evolution-agent: using Vault AppRole authentication")
            self._authenticate_with_approle()
        else:
            # Fallback: статический токен
            self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
            self.token_expires_at = None
            logger.info("🔐 evolution-agent: falling back to Vault token authentication")
            if not self.vault_token:
                raise ValueError(
                    "Vault token is required when AppRole credentials are not provided"
                )

        self._wait_for_vault()

    def _authenticate_with_approle(self) -> None:
        """Аутентификация в Vault через AppRole и получение client_token."""
        try:
            auth_data = {"role_id": self.role_id, "secret_id": self.secret_id}
            resp = requests.post(
                f"{self.vault_addr}/v1/auth/approle/login", json=auth_data, timeout=5
            )
            resp.raise_for_status()

            data = resp.json()["auth"]
            self.vault_token = data["client_token"]
            lease_duration = data["lease_duration"]
            # Обновляем токен за 5 минут до истечения
            self.token_expires_at = time.time() + lease_duration - 300

            logger.info(
                "✅ evolution-agent: Vault AppRole authentication successful "
                f"(lease {lease_duration}s)"
            )
        except Exception as e:
            logger.error(f"❌ evolution-agent: AppRole authentication failed: {e}")
            raise

    def _wait_for_vault(self, max_attempts: int = 30, delay: int = 2) -> None:
        """Ожидаем доступности Vault (health endpoint), чтобы избежать гонок на старте."""
        for attempt in range(max_attempts):
            try:
                resp = requests.get(
                    f"{self.vault_addr}/v1/sys/health",
                    headers={"X-Vault-Token": self.vault_token},
                    timeout=3,
                )
                if resp.status_code in (200, 429):
                    logger.info("🔎 evolution-agent: Vault is available")
                    return
            except Exception:
                pass

            if attempt < max_attempts - 1:
                logger.info(
                    f"⌛ evolution-agent: waiting for Vault... "
                    f"{attempt + 1}/{max_attempts}"
                )
                time.sleep(delay)
            else:
                logger.error("❌ evolution-agent: Vault is not available")
                # Не поднимаем исключение, чтобы локальная разработка могла стартовать

    def _is_token_valid(self) -> bool:
        if not self.vault_token:
            return False
        if self.token_expires_at is None:
            return True
        return time.time() < self.token_expires_at

    def _refresh_token_if_needed(self) -> None:
        if not self._is_token_valid() and self.role_id and self.secret_id:
            logger.info("🔄 evolution-agent: refreshing Vault token via AppRole...")
            self._authenticate_with_approle()

    def get_secret(self, path: str) -> Dict[str, Any]:
        """
        Получить секрет из KV v2 по логическому пути `path`.

        Пример: path="jwt" → фактический URL `kv/data/jwt`.
        """
        self._refresh_token_if_needed()

        full_path = f"kv/data/{path}"
        url = f"{self.vault_addr}/v1/{full_path}"
        headers = {"X-Vault-Token": self.vault_token}

        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 403 and self.role_id and self.secret_id:
                # пробуем перелогиниться по AppRole
                logger.warning(
                    "⚠ evolution-agent: Vault returned 403, trying to re-authenticate"
                )
                self._authenticate_with_approle()
                headers = {"X-Vault-Token": self.vault_token}
                resp = requests.get(url, headers=headers, timeout=5)

            resp.raise_for_status()
            return resp.json()["data"]["data"]
        except Exception as e:
            logger.error(f"❌ evolution-agent: failed to read secret '{path}' from Vault: {e}")
            raise


_vault_client: Optional[ServiceVaultClient] = None


def get_vault_client() -> ServiceVaultClient:
    global _vault_client
    if _vault_client is None:
        _vault_client = ServiceVaultClient()
    return _vault_client

