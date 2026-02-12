import logging
from typing import Any, Dict, List

from app.core.llm import get_llm_research
from app.core.prompts import prompt_registry
from app.schemas.runtime import TaskRuntimeContext

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    Research Agent: собирает контекст и извлекает инсайты через Gemini 1.5 Flash.

    Пока items — заглушка; позже подключается parsing-service.
    Инсайты генерируются реальным LLM (Gemini).
    """

    async def run_research(self, ctx: TaskRuntimeContext) -> Dict[str, Any]:
        # TODO: интеграция с parsing-service → подставить реальные items
        items: List[Dict[str, Any]] = [
            {"source": "stub", "text": "Популярные посты про автоматизацию маркетинга."},
            {"source": "stub", "text": "Аудитория хорошо реагирует на пошаговые инструкции."},
        ]

        llm = get_llm_research()
        prompt = prompt_registry.render("research_insights_v1", {"items": items})
        messages = [
            {"role": "user", "content": prompt},
        ]
        try:
            out = await llm.chat_json(messages=messages)
            insights = out.get("insights") or []
        except Exception as e:
            logger.warning("Research Agent (Gemini) fallback to stub insights: %s", e)
            insights = [
                "Использовать понятный, человеческий язык без перегруза терминами.",
                "Чередовать образовательные и более лёгкие, вдохновляющие посты.",
            ]
        return {"items": items, "insights": insights}

