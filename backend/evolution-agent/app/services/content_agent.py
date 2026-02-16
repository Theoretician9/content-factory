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
        persona = ctx.persona or {"tone": "friendly_expert", "language": "ru", "forbidden_topics": []}
        strategy = ctx.strategy_snapshot or {}
        feedback = (ctx.feedback or "").strip()

        # Описание канала: сначала берём то, что пришло с онбординга (channel_description),
        # если его нет — используем общий fallback.
        channel_description = None
        if isinstance(persona, dict):
            channel_description = persona.get("channel_description")
        if not channel_description:
            channel_description = "Автоматическое ведение Telegram‑канала."

        prompt = prompt_registry.render(
            "content_writer_v1",
            {
                "persona": persona,
                "strategy": strategy,
                "pillar": None,
                "description": channel_description,
            },
        )

        if feedback:
            prompt += (
                "\n\nADDITIONAL USER FEEDBACK / INSTRUCTIONS FOR THIS POST:\n"
                f"{feedback}\n"
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

