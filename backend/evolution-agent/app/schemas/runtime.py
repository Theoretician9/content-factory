from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class TaskRuntimeContext(BaseModel):
    """
    Оперативный контекст задачи генерации слота (см. ТЗ, раздел 7.1).
    Хранится в памяти/Redis, при необходимости может снапшотиться в БД.
    """

    task_id: UUID
    user_id: int
    channel_id: str
    slot_id: UUID

    current_step: str  # init / research / draft / validate / publish / done / error

    persona: Optional[Dict[str, Any]] = None
    strategy_snapshot: Optional[Dict[str, Any]] = None
    research_data: List[Dict[str, Any]] = []
    insights: List[str] = []
    draft_content: Optional[str] = None
    errors: List[str] = []
    decisions_log: List[str] = []

