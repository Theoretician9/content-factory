from typing import Any, Dict, List, Optional

import httpx


class LLMClient:
    """
    Минимальный LLM‑клиент.

    В рамках MVP оставляем абстракцию + точку расширения;
    конкретную реализацию (OpenAI/Gemini/локальная) можно подставить позже.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or "https://api.openai.com/v1"
        self.api_key = api_key  # для реальной интеграции возьмём из Vault

    async def chat_json(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Асинхронный вызов LLM, который ожидает JSON‑ответ.

        Сейчас это заглушка: возвращает фиксированную структуру,
        чтобы можно было построить оркестратор без реального LLM.
        """
        # TODO: подключить реальный HTTP‑клиент к выбранному LLM‑провайдеру.
        # Пока возвращаем простейший «пост» для MVP‑пайплайна.
        return {
            "post_text": "Заглушка evolution-agent: здесь будет сгенерированный текст поста.",
            "hashtags": ["#content_factory", "#evolution_agent"],
            "cta": "Подписывайтесь на канал, дальше будет интереснее!",
        }

