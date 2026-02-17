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

        payload: Dict[str, Any] = {
            "text": text,
            # parse_mode и disable_web_page_preview оставляем по умолчанию
        }

        # Нормализуем channel_id:
        # - если это чисто число/строка-число → отправляем как numeric channel_id
        # - иначе считаем, что это username/ссылка и отправляем как channel (строковое поле)
        if isinstance(channel_id, int):
            payload["channel_id"] = channel_id
        elif isinstance(channel_id, str):
            raw = channel_id.strip()
            # Если строка состоит только из цифр, трактуем как numeric ID
            if raw.isdigit():
                payload["channel_id"] = int(raw)
            else:
                # Любой другой формат (t.me/..., @username, текст) отправляем как channel
                payload["channel"] = raw
        else:
            raise ValueError(f"Unsupported channel_id type: {type(channel_id)}")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)

            # Хотим видеть, ПОЧЕМУ integration-service вернул 4xx/5xx
            if resp.status_code >= 400:
                # В логах evolution-agent окажется и статус, и тело ошибки (detail из FastAPI)
                raise httpx.HTTPStatusError(
                    f"{resp.status_code} {resp.reason_phrase} while calling "
                    f"{url} with payload={payload!r}. Response body: {resp.text}",
                    request=resp.request,
                    response=resp,
                )

            return resp.json()

