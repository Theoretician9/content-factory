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

    def render(self, name: str, context: Dict[str, Any]) -> str:
        if name not in self._templates:
            raise KeyError(f"Prompt template '{name}' is not registered")
        return self._templates[name].template.render(**context)


prompt_registry = PromptTemplateRegistry()

