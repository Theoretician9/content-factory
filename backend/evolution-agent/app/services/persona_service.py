"""
Генерация persona и стратегии через Llama 3.1 8B (Groq).
Используется при онбординге агента для канала.
"""
import logging
from typing import Any, Dict

from app.core.llm import get_llm_persona
from app.core.prompts import prompt_registry

logger = logging.getLogger(__name__)


async def generate_persona_and_strategy(
    description: str,
    tone: str = "friendly_expert",
    language: str = "ru",
) -> Dict[str, Any]:
    """
    Генерирует persona_json, content_mix_json, schedule_rules_json через Llama 3.1 8B.
    При ошибке или невалидном ответе возвращает None (вызывающий использует fallback).
    """
    try:
        prompt = prompt_registry.render(
            "persona_strategy_v1",
            {"description": description, "tone": tone, "language": language},
        )
        llm = get_llm_persona()
        out = await llm.chat_json(messages=[{"role": "user", "content": prompt}])
        persona = out.get("persona_json")
        content_mix = out.get("content_mix_json")
        schedule_rules = out.get("schedule_rules_json")
        if not persona or not content_mix or not schedule_rules:
            logger.warning("Persona LLM returned incomplete keys: %s", list(out.keys()))
            return None
        return {
            "persona_json": persona,
            "content_mix_json": content_mix,
            "schedule_rules_json": schedule_rules,
        }
    except Exception as e:
        logger.warning("Persona/Strategy generation (Llama) failed, use fallback: %s", e)
        return None
