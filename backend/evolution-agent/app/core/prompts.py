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
        # === Content Writer v1 (расширенный промпт с историей и инсайтами) ===
        content_writer = Template(
            (
                "You are the persona below, writing a Telegram post as a real human author.\n\n"
                "PERSONA JSON:\n"
                "{{ persona | tojson }}\n\n"
                "STRATEGY SNAPSHOT (may include pillars/series):\n"
                "{{ strategy | tojson }}\n\n"
                "{% if pillar %}CURRENT PILLAR ID: {{ pillar }}{% endif %}\n"
                "{% if series %}\n"
                "CURRENT SERIES:\n"
                "{{ series | tojson }}\n"
                "{% endif %}\n"
                "{% if previous_posts %}\n"
                "PREVIOUS POSTS SUMMARY (for context, do NOT repeat them literally):\n"
                "{% for p in previous_posts %}- [{{ p.created_at }}] {{ p.short_summary }}\n{% endfor %}\n"
                "{% endif %}\n"
                "{% if source_snippets %}\n"
                "TOPIC‑RELEVANT TELEGRAM POSTS (use as factual base; do NOT copy them verbatim):\n"
                "{% for s in source_snippets %}- [eng={{ s.engagement_total }} views={{ s.views_count }}] {{ s.text }}\n{% endfor %}\n"
                "{% endif %}\n"
                "{% if insights %}\n"
                "RESEARCH INSIGHTS YOU SHOULD USE (weave 1–2 into the post naturally, not as dry bullet list):\n"
                "{% for ins in insights %}- {{ ins }}\n{% endfor %}\n"
                "{% endif %}\n"
                "{% if feedback %}\n"
                "USER FEEDBACK / SPECIAL INSTRUCTIONS FOR THIS PARTICULAR POST:\n"
                "{{ feedback }}\n"
                "{% endif %}\n\n"
                "TASK:\n"
                "- Write ONE Telegram post in {{ persona.language or 'ru' }} that fits the persona, strategy and current context.\n"
                "- The text must feel like it comes from a single human over time, not from an AI template.\n\n"
                "STRUCTURE CONSTRAINTS:\n"
                "1) Hook (first 1–2 sentences):\n"
                "   - can be a vivid short scene from the author's or reader's life, OR\n"
                "   - a strong opinion, OR\n"
                "   - a concrete pain of the audience.\n"
                "   DO NOT start with generic meta‑phrases like \"В этом посте я расскажу\", \"Сегодня поговорим\", \"В этом посте мы рассмотрим\".\n"
                "   DO NOT start every post with a rhetorical question of the form \"Вы когда‑нибудь задумывались...\".\n"
                "2) Middle part (2–5 short paragraphs):\n"
                "   - 1–3 specific ideas, frameworks or micro‑stories,\n"
                "   - at least one concrete, practical takeaway the reader can apply,\n"
                "   - if you use numbers, keep them simple and realistic and avoid fake \"по статистике\" claims unless they clearly come from the research insights above.\n"
                "3) Ending:\n"
                "   - 1–2 sentences that либо подводят понятный вывод, либо задают сильный вопрос для рефлексии,\n"
                "   - a natural CTA aligned with persona (приглашение поделиться опытом, задать вопрос, попробовать приём из поста),\n"
                "   - DO NOT promise \"в следующих постах\" или \"на следующей неделе мы поговорим\" если вы не ссылаетесь на конкретную серию.\n\n"
                "STYLE CONSTRAINTS:\n"
                "- Max length: 1500 characters of body text.\n"
                "- Forbidden topics: {{ (persona.forbidden_topics or []) | join(', ') if persona.forbidden_topics is defined else '' }}.\n"
                "- Vary sentence length and paragraph length.\n"
                "- Allow spoken, natural language if persona allows it.\n"
                "- Avoid over‑formal academic tone unless persona explicitly requires it.\n"
                "- Avoid repeating the same opening patterns across posts. If previous_posts show a certain hook style, choose a different one here.\n"
                "- Prefer concrete, experience‑based examples over abstract generalisations.\n\n"
                "OUTPUT FORMAT (strict JSON, no markdown, no comments):\n"
                "{\n"
                "  \"post_text\": \"full text of the post as one string with \\n for line breaks\",\n"
                "  \"hashtags\": [\"up to 5 relevant hashtags without # in the text body\"],\n"
                "  \"cta\": \"1–2 sentences CTA at the end, in the same tone as the post\"\n"
                "}\n"
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

        # Persona/Strategy: из описания канала сгенерировать глубокую persona, content_mix, schedule_rules
        persona_strategy = Template(
            "You are a senior content strategist and brand copywriter for Telegram channels.\n"
            "Your task is to design BOTH a deep, realistic AUTHOR PERSONA and a MID‑TERM CONTENT STRATEGY.\n\n"
            "INPUT DATA FROM USER:\n"
            "- Channel description: {{ description }}\n"
            "- Desired tone of voice: {{ tone }}\n"
            "- Interface language: {{ language }}\n\n"
            "OVERALL GOAL:\n"
            "- Build a channel that keeps the target audience engaged for at least 3–6 months,\n"
            "  with posts that feel like a continuous story instead of isolated templates.\n\n"
            "GENERAL REQUIREMENTS:\n"
            "1) Think as a strategist, not as a generic AI assistant.\n"
            "2) Persona must look like a real human with background, worldview and typical behavior.\n"
            "3) Strategy must define clear content pillars, recurring series and a weekly posting pattern.\n"
            "4) All output MUST be valid JSON (one object), no markdown, no comments, no trailing commas.\n\n"
            "Return EXACTLY ONE JSON object with the following top‑level keys:\n"
            "  persona_json,\n"
            "  content_mix_json,\n"
            "  schedule_rules_json.\n\n"
            "persona_json MUST have the following structure:\n"
            "{\n"
            "  \"identity\": {\n"
            "    \"name\": \"short label for the author (e.g. 'основатель B2B‑SaaS')\",\n"
            "    \"role\": \"how the audience sees this person\",\n"
            "    \"background\": \"1–3 sentences of realistic background and experience\"\n"
            "  },\n"
            "  \"audience\": {\n"
            "    \"who\": \"who are the readers\",\n"
            "    \"level\": \"beginner / middle / advanced (pick one)\",\n"
            "    \"pains\": [\"3–7 specific pains\"],\n"
            "    \"goals\": [\"3–7 concrete goals\"]\n"
            "  },\n"
            "  \"tone\": \"detailed tone of voice (e.g. 'дружелюбный, прямой, с лёгкой иронией')\",\n"
            "  \"language\": \"{{ language }}\",\n"
            "  \"voice\": {\n"
            "    \"style_markers\": [\"5–10 recognisable writing patterns\"],\n"
            "    \"taboos\": [\"what this persona NEVER does in content\"]\n"
            "  },\n"
            "  \"content_positioning\": {\n"
            "    \"main_topic\": \"main topic of the channel\",\n"
            "    \"subtopics\": [\"2–7 supporting subtopics\"],\n"
            "    \"differentiation\": \"what makes this channel different from others\"\n"
            "  },\n"
            "  \"narrative\": {\n"
            "    \"long_term_theme\": \"what multi‑month story we are telling\",\n"
            "    \"recurring_series\": [\n"
            "      {\n"
            "        \"id\": \"short_machine_readable_id\",\n"
            "        \"name\": \"human readable series name\",\n"
            "        \"description\": \"what this series is about\",\n"
            "        \"typical_format\": \"e.g. 'кейс + конкретный план'\"\n"
            "      }\n"
            "    ]\n"
            "  },\n"
            "  \"forbidden_topics\": [\"topics the author must avoid\"],\n"
            "  \"channel_description\": \"{{ description }}\"\n"
            "}\n\n"
            "content_mix_json MUST have the following structure:\n"
            "{\n"
            "  \"pillars\": [\n"
            "    {\n"
            "      \"id\": \"short_machine_readable_id\",\n"
            "      \"name\": \"human readable name\",\n"
            "      \"weight\": 0.0,\n"
            "      \"goal\": \"what this pillar achieves for the audience\",\n"
            "      \"formats\": [\"post formats used in this pillar\"],\n"
            "      \"series\": [\n"
            "        {\n"
            "          \"id\": \"series_id\",\n"
            "          \"name\": \"series name\",\n"
            "          \"goal\": \"what long‑term transformation this series aims for\",\n"
            "          \"episode_types\": [\"types of episodes inside this series\"],\n"
            "          \"recommended_hook_styles\": [\"hook patterns that work best here\"]\n"
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "schedule_rules_json MUST have the following structure:\n"
            "{\n"
            "  \"posts_per_day\": 1,\n"
            "  \"preferred_hours\": [11],\n"
            "  \"timezone\": \"either 'UTC' or a specific tz like 'Europe/Moscow'\",\n"
            "  \"weekly_pattern\": {\n"
            "    \"mon\": [\"pillar_id\", \"pillar_id\"],\n"
            "    \"tue\": [\"pillar_id\"],\n"
            "    \"wed\": [\"pillar_id\"],\n"
            "    \"thu\": [\"pillar_id\"],\n"
            "    \"fri\": [\"pillar_id\"],\n"
            "    \"sat\": [\"pillar_id\"],\n"
            "    \"sun\": [\"pillar_id\"]\n"
            "  }\n"
            "}\n\n"
            "Respond with a single JSON object:\n"
            "{\n"
            "  \"persona_json\": { ... as specified above ... },\n"
            "  \"content_mix_json\": { ... as specified above ... },\n"
            "  \"schedule_rules_json\": { ... as specified above ... }\n"
            "}\n"
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

