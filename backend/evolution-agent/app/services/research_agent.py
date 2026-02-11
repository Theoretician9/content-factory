from typing import Any, Dict, List

from app.schemas.runtime import TaskRuntimeContext


class ResearchAgent:
    """
    Research Agent: собирает и нормализует внешний контекст.

    Для текущего MVP в качестве заглушки возвращает фиктивные инсайты,
    чтобы оркестратор мог последовательно проходить шаг research → content.
    """

    async def run_research(self, ctx: TaskRuntimeContext) -> Dict[str, Any]:
        # TODO: интеграция с parsing-service / другими источниками
        fake_items: List[Dict[str, Any]] = [
            {"source": "stub", "text": "Популярные посты про автоматизацию маркетинга."},
            {"source": "stub", "text": "Аудитория хорошо реагирует на пошаговые инструкции."},
        ]
        insights = [
            "Использовать понятный, человеческий язык без перегруза терминами.",
            "Чередовать образовательные и более лёгкие, вдохновляющие посты.",
        ]
        return {"items": fake_items, "insights": insights}

