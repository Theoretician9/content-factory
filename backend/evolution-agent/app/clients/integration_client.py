from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings


class IntegrationServiceClient:
    """
    HTTP‑клиент для обращения к integration-service из evolution-agent.

    Через него будем отправлять посты в Telegram (`/api/v1/telegram/messages/send`).
    """

    def __init__(self, base_url: Optional[str] = None):
        settings = get_settings()
        self.base_url = base_url or "http://integration-service:8000"
        # evolution-agent работает за api-gateway, но внутри backend-сети
        # удобнее ходить напрямую в integration-service.

    async def send_telegram_message(
        self,
        jwt_token: str,
        text: str,
        channel_id: str | int,
    ) -> Dict[str, Any]:
        """
        Вызов `POST /api/v1/telegram/messages/send` в integration-service.

        Пока схема запроса минимальна и использует только `text`, остальные
        поля `SendMessageRequest` заполняются значениями по умолчанию.
        """
        url = f"{self.base_url}/api/v1/telegram/messages/send"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
        }

        # Integration Service ожидает numeric channel_id (int).
        # Если нам передали ссылку/username (t.me/... или @channel), публикация
        # через этот endpoint не сработает. Явно логируем предупреждение.
        if isinstance(channel_id, str):
            # Обрезаем возможные префиксы, но не приводим к int автоматически —
            # это должен быть real numeric ID, который уже есть в integration-service.
            normalized = channel_id.replace("https://t.me/", "").replace("http://t.me/", "")
            normalized = normalized.lstrip("@")
            # Логируем для отладки; сам numeric id должен быть получен через integration-service.
            print(
                f"⚠ evolution-agent: send_telegram_message получил channel_id='{channel_id}', "
                f"Integration Service ожидает numeric ID (int). "
                "Убедись, что в стратегии/канале сохранён numeric channel_id из integration-service."
            )
            # Оставляем исходный channel_id — integration-service вернёт 422, если тип не int.

        payload = {
            "text": text,
            "channel_id": channel_id,
            # parse_mode и disable_web_page_preview оставляем по умолчанию
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

