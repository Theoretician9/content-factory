import logging
from typing import Any, Dict, List

from app.clients.parsing_client import ParsingServiceClient
from app.core.llm import get_llm_research
from app.core.prompts import prompt_registry
from app.schemas.runtime import TaskRuntimeContext

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    Research Agent: собирает контекст из parsing-service и извлекает инсайты через Gemini 1.5 Flash.

    При недоступности parsing-service или отсутствии данных использует безопасный stub‑fallback.
    """

    def __init__(self, parsing_client: ParsingServiceClient | None = None) -> None:
        self._parsing_client = parsing_client or ParsingServiceClient()

    async def run_research(self, ctx: TaskRuntimeContext) -> Dict[str, Any]:
        # 1. Пытаемся получить реальные данные из parsing-service
        items: List[Dict[str, Any]] = []
        try:
            if ctx.user_id:
                items = await self._parsing_client.get_recent_telegram_snippets(
                    user_id=ctx.user_id,
                    max_tasks=3,
                    max_results_per_task=20,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("Research Agent: parsing-service unavailable, using stub data: %s", e)

        # Если parsing-service не дал данных — используем stub для стабильности пайплайна
        if not items:
            items = [
                {"source": "stub", "text": "Популярные посты про автоматизацию маркетинга."},
                {"source": "stub", "text": "Аудитория хорошо реагирует на пошаговые инструкции."},
            ]

        # 2. Gemini 1.5 Flash → извлечение инсайтов из items
        llm = get_llm_research()
        prompt = prompt_registry.render("research_insights_v1", {"items": items})
        messages = [
            {"role": "user", "content": prompt},
        ]
        try:
            out = await llm.chat_json(messages=messages)
            insights = out.get("insights") or []
        except Exception as e:  # noqa: BLE001
            logger.warning("Research Agent (Gemini) fallback to stub insights: %s", e)
            insights = [
                "Использовать понятный, человеческий язык без перегруза терминами.",
                "Чередовать образовательные и более лёгкие, вдохновляющие посты.",
            ]
        return {"items": items, "insights": insights}


