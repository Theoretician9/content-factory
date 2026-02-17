from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import jwt

from app.core.vault import get_vault_client


class ParsingServiceClient:
    """
    HTTP‑клиент для обращения к parsing-service из evolution-agent.

    Используется Research Agent для получения реальных сниппетов
    из результатов парсинга Telegram‑каналов пользователя.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        # evolution-agent работает во внутренней сети backend,
        # поэтому идём напрямую в parsing-service.
        self.base_url = base_url or "http://parsing-service:8000"

    async def _get_jwt_token(self, user_id: int) -> str:
        """
        Получить JWT токен для обращения к parsing-service.

        Схема аналогична invite-service: берём секрет из Vault (`jwt.secret_key`)
        и подписываем payload с user_id и service= evolution-agent.
        """
        vault_client = get_vault_client()
        secret_data = vault_client.get_secret("jwt")
        secret_key = secret_data.get("secret_key")
        if not secret_key:
            raise RuntimeError("JWT secret_key not found in Vault for parsing-service client")

        now = datetime.utcnow()
        payload = {
            "service": "evolution-agent",
            "user_id": user_id,
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, secret_key, algorithm="HS256")
        return token

    async def get_recent_telegram_snippets(
        self,
        user_id: int,
        max_tasks: int = 3,
        max_results_per_task: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Получить последние сниппеты из результатов парсинга Telegram‑каналов пользователя.

        Алгоритм:
        1. /api/v1/results/grouped — список задач парсинга пользователя.
        2. Для последних N задач → /results/{task_id} — подробные результаты.
        3. Преобразовать в формат items для Research Agent:
           {source: 'telegram_channel', text: '...', ts: '...'}.
        """
        token = await self._get_jwt_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        items: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Получаем задачи парсинга пользователя
            grouped_url = f"{self.base_url}/api/v1/results/grouped"
            grouped_resp = await client.get(grouped_url, headers=headers)
            grouped_resp.raise_for_status()
            data = grouped_resp.json()
            tasks = data.get("tasks", [])

            # Берём несколько последних задач (они уже отсортированы по created_at desc)
            for task in tasks[:max_tasks]:
                task_id = task.get("task_id")
                if not task_id:
                    continue

                # 2. Получаем результаты конкретной задачи
                results_url = f"{self.base_url}/results/{task_id}"
                results_resp = await client.get(
                    results_url,
                    headers=headers,
                    params={"limit": max_results_per_task},
                )
                if results_resp.status_code != 200:
                    continue
                res_data = results_resp.json()
                results = res_data.get("results", [])

                for r in results:
                    platform = r.get("platform")
                    if platform and str(platform).lower() != "telegram":
                        continue

                    platform_data = r.get("platform_specific_data") or {}
                    # Пытаемся извлечь максимально информативный текст:
                    # - message / text в platform_specific_data
                    # - либо display_name / username.
                    text: str = (
                        platform_data.get("message")
                        or platform_data.get("text")
                        or r.get("display_name")
                        or r.get("username")
                        or ""
                    )
                    if not text:
                        continue

                    item_ts = r.get("created_at")

                    items.append(
                        {
                            "source": "telegram_channel",
                            "text": text,
                            "ts": item_ts,
                            "task_id": task_id,
                        }
                    )

        return items

    async def get_topic_telegram_snippets(
        self,
        user_id: int,
        topic: str,
        limit: int = 50,
        min_engagement: int = 0,
        min_views: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Получить популярные Telegram‑посты пользователя по заданной теме.

        Использует новый endpoint parsing-service:
        POST /api/v1/research/telegram/snippets
        """
        token = await self._get_jwt_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        payload: Dict[str, Any] = {
            "topic": topic,
            "limit": limit,
            "min_engagement": min_engagement,
            "min_views": min_views,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{self.base_url}/api/v1/research/telegram/snippets"
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json() or {}

        items: List[Dict[str, Any]] = []
        for r in data.get("items", []):
            text = (r.get("text") or "").strip()
            if not text:
                continue

            items.append(
                {
                    "source": "telegram_post",
                    "channel_id": r.get("channel_id"),
                    "channel_name": r.get("channel_name"),
                    "text": text,
                    "ts": r.get("ts"),
                    "engagement_total": r.get("engagement_total", 0),
                    "views_count": r.get("views_count", 0),
                    "likes_count": r.get("likes_count", 0),
                    "comments_count": r.get("comments_count", 0),
                    "reactions_count": r.get("reactions_count", 0),
                }
            )

        return items

