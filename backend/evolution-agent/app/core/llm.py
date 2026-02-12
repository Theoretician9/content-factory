"""
LLM‑провайдеры для evolution-agent.

- Research Agent  → Gemini 1.5 Flash (Google)
- Content Agent   → GPT-4o-mini (OpenAI)
- Persona/Strategy → Llama 3.1 8B (Groq)
Ключи и настройки загружаются из Vault (config).
"""
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Модели по назначению (как в ТЗ)
MODEL_RESEARCH = "gemini-1.5-flash"
MODEL_CONTENT = "gpt-4o-mini"
MODEL_PERSONA = "llama-3.1-8b-instant"


class BaseLLMProvider(ABC):
    """Базовый интерфейс: асинхронный вызов с ожиданием JSON-ответа."""

    @abstractmethod
    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Вызов модели и парсинг ответа как JSON."""
        ...


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """Достаёт JSON из текста (в т.ч. из markdown-блока)."""
    text = text.strip()
    # Блок ```json ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return json.loads(m.group(1).strip())
    # Иначе ищем первый { ... }
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    return json.loads(text)


class OpenAIProvider(BaseLLMProvider):
    """GPT-4o-mini через OpenAI API (Content Agent)."""

    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_CONTENT):
        self._api_key = api_key or get_settings().OPENAI_API_KEY
        self._model = model
        if not self._api_key:
            logger.warning("evolution-agent: OPENAI_API_KEY not set, Content Agent calls will fail")

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key)
        resp = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"} if response_schema else None,
        )
        text = (resp.choices[0].message.content or "").strip()
        return _extract_json_from_text(text)


class GeminiProvider(BaseLLMProvider):
    """Gemini 1.5 Flash (Research Agent)."""

    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_RESEARCH):
        self._api_key = api_key or get_settings().GEMINI_API_KEY
        self._model = model
        if not self._api_key:
            logger.warning("evolution-agent: GEMINI_API_KEY not set, Research Agent calls will fail")

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        import google.generativeai as genai

        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model)
        # Gemini ожидает parts; из messages собираем единый prompt для простоты
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                parts.append(f"[System]\n{content}\n")
            else:
                parts.append(content)
        prompt = "\n".join(parts)
        response = await model.generate_content_async(prompt)
        text = (response.text or "").strip()
        return _extract_json_from_text(text)


class GroqProvider(BaseLLMProvider):
    """Llama 3.1 8B через Groq API (Persona/Strategy)."""

    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_PERSONA):
        self._api_key = api_key or get_settings().GROQ_API_KEY
        self._model = model
        if not self._api_key:
            logger.warning("evolution-agent: GROQ_API_KEY not set, Persona/Strategy calls will fail")

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=self._api_key)
        resp = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
        )
        text = (resp.choices[0].message.content or "").strip()
        return _extract_json_from_text(text)


def get_llm_research() -> BaseLLMProvider:
    """Research Agent → Gemini 1.5 Flash."""
    return GeminiProvider(model=MODEL_RESEARCH)


def get_llm_content() -> BaseLLMProvider:
    """Content Agent → GPT-4o-mini."""
    return OpenAIProvider(model=MODEL_CONTENT)


def get_llm_persona() -> BaseLLMProvider:
    """Persona/Strategy → Llama 3.1 8B (Groq)."""
    return GroqProvider(model=MODEL_PERSONA)


# Обратная совместимость: LLMClient = Content-провайдер по умолчанию
class LLMClient:
    """
    Обёртка для Content Agent (GPT-4o-mini).
    Сохраняет интерфейс chat_json(model=..., messages=..., response_schema=...).
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self._provider = llm_provider or get_llm_content()

    async def chat_json(
        self,
        model: str = MODEL_CONTENT,
        messages: Optional[List[Dict[str, str]]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if messages is None:
            messages = []
        return await self._provider.chat_json(
            messages=messages,
            response_schema=response_schema,
        )
