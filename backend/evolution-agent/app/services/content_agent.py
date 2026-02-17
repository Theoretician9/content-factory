from typing import Any, Dict

from app.core.llm import LLMClient, MODEL_CONTENT
from app.core.prompts import prompt_registry
from app.schemas.runtime import TaskRuntimeContext


class ContentAgent:
    """
    Content Agent: генерирует текст поста через GPT-4o-mini (OpenAI).
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or LLMClient()

    async def generate_post(self, ctx: TaskRuntimeContext) -> Dict[str, Any]:
        """Собрать промпт и получить черновик поста (JSON)."""
        persona = ctx.persona or {
            "tone": "friendly_expert",
            "language": "ru",
            "forbidden_topics": [],
        }
        strategy = ctx.strategy_snapshot or {}
        feedback = (ctx.feedback or "").strip()
        insights = ctx.insights or []
        previous_posts = ctx.previous_posts or []

        # Описание канала: сначала берём то, что пришло с онбординга (channel_description).
        # Никаких жёстко зашитых заглушек — если описания нет, считаем это ошибкой конфигурации.
        channel_description = None
        if isinstance(persona, dict):
            channel_description = persona.get("channel_description")
        if not channel_description:
            raise ValueError(
                "Persona.channel_description is not set. "
                "Онбординг канала должен передавать текстовое описание, иначе пост генерировать нельзя."
            )

        prompt = prompt_registry.render(
            "content_writer_v1",
            {
                "persona": persona,
                "strategy": strategy,
                "pillar": ctx.pillar_id,
                "series": ctx.series_info,
                "description": channel_description,
                "feedback": feedback,
                "insights": insights,
                "previous_posts": previous_posts,
            },
        )

        messages = [
            {"role": "system", "content": "You are an assistant that writes Telegram posts. Reply with JSON only."},
            {"role": "user", "content": prompt},
        ]

        result = await self._llm.chat_json(
            model=MODEL_CONTENT,
            messages=messages,
            response_schema={"type": "object"},
        )
        return result

