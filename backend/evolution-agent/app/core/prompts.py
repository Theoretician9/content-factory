from dataclasses import dataclass
from typing import Any, Dict, List

from jinja2 import Template


@dataclass
class PromptTemplate:
    name: str
    template: Template


class PromptTemplateRegistry:
    """
    Простейший регистр шаблонов промптов.

    Для MVP храним шаблоны в коде; позже можно вынести в YAML/Jinja2‑файлы.
    """

    def __init__(self) -> None:
        self._templates: Dict[str, PromptTemplate] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        content_writer = Template(
            (
                "You are a {{ persona.tone }} Telegram channel author.\n"
                "Language: {{ persona.language }}.\n"
                "Topic description: {{ description }}.\n"
                "Current slot pillar: {{ pillar or 'general' }}.\n\n"
                "CONSTRAINTS:\n"
                "- Max length: 1500 characters.\n"
                "- Forbidden topics: {{ persona.forbidden_topics | join(', ') }}.\n\n"
                "REQUIREMENTS:\n"
                "- Return strict JSON: "
                '{"post_text": "...", "hashtags": [], "cta": "..."}.\n'
            )
        )
        self._templates["content_writer_v1"] = PromptTemplate(
            name="content_writer_v1",
            template=content_writer,
        )

        # Research: из сырых items извлечь инсайты (JSON)
        research_insights = Template(
            "Based on the following research items (snippets from articles/social), "
            "extract 3–5 short, actionable insights for writing a Telegram post.\n"
            "Items:\n{% for item in items %}- [{{ item.source }}] {{ item.text }}\n{% endfor %}\n"
            "Respond with JSON only: {\"insights\": [\"insight 1\", \"insight 2\", ...]}"
        )
        self._templates["research_insights_v1"] = PromptTemplate(
            name="research_insights_v1",
            template=research_insights,
        )

        # Persona/Strategy: из описания канала сгенерировать persona, content_mix, schedule_rules
        persona_strategy = Template(
            "Generate a content strategy for a Telegram channel.\n"
            "Channel description: {{ description }}\n"
            "Tone: {{ tone }}\n"
            "Language: {{ language }}\n\n"
            "Respond with a single JSON object with exactly these keys (no other keys):\n"
            '"persona_json": {"tone": "...", "language": "{{ language }}", "forbidden_topics": []},\n'
            '"content_mix_json": {"education": 0.0-1.0, "opinion": 0.0-1.0, "news": 0.0-1.0},\n'
            '"schedule_rules_json": {"posts_per_day": 1, "preferred_hours": [11], "timezone": "UTC"}.\n'
            "Use only valid JSON, no markdown."
        )
        self._templates["persona_strategy_v1"] = PromptTemplate(
            name="persona_strategy_v1",
            template=persona_strategy,
        )

    def render(self, name: str, context: Dict[str, Any]) -> str:
        if name not in self._templates:
            raise KeyError(f"Prompt template '{name}' is not registered")
        return self._templates[name].template.render(**context)


prompt_registry = PromptTemplateRegistry()

