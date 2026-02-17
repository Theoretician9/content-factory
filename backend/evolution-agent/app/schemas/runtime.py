from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class TaskRuntimeContext(BaseModel):
    """
    Оперативный контекст задачи генерации слота (см. ТЗ, раздел 7.1).
    Хранится в памяти/Redis, при необходимости может снапшотиться в БД.

    Расширен для более «человечной» генерации:
    - previous_posts: краткая история последних постов для связности;
    - pillar/series: информация о тематическом столпе/серии (если доступна).
    """

    task_id: UUID
    user_id: int
    channel_id: str
    slot_id: UUID

    current_step: str  # init / research / draft / validate / publish / done / error

    # Дополнительные указания/фидбек от пользователя (используется при регенерации слота)
    feedback: Optional[str] = None

    persona: Optional[Dict[str, Any]] = None
    strategy_snapshot: Optional[Dict[str, Any]] = None
    research_data: List[Dict[str, Any]] = []
    insights: List[str] = []

    # Краткая история последних постов по каналу
    previous_posts: List[Dict[str, Any]] = []

    # Опциональная информация о тематическом столпе / серии (если будет использоваться)
    pillar_id: Optional[str] = None
    series_info: Optional[Dict[str, Any]] = None

    draft_content: Optional[str] = None
    errors: List[str] = []
    decisions_log: List[str] = []

