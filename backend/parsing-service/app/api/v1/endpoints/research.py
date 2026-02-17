"""
Research endpoints for evolution-agent: themed, high-engagement Telegram snippets.
"""

from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.parse_result import ParseResult
from app.models.parse_task import ParseTask
from app.core.auth import get_user_id_from_request
from app.core.config import Platform


router = APIRouter()


class TelegramResearchRequest(BaseModel):
    """Запрос на подбор подходящих Telegram‑постов для темы."""

    topic: str = Field(..., min_length=3, description="Текстовое описание темы/ниши канала")
    limit: int = Field(50, ge=1, le=200, description="Максимум постов")
    min_engagement: int = Field(0, ge=0, description="Минимальный суммарный engagement (лайки+комменты+реакции)")
    min_views: int = Field(0, ge=0, description="Минимальное количество просмотров")


class TelegramSnippet(BaseModel):
    """Нормализованный сниппет Telegram‑поста для ResearchAgent."""

    source: str
    channel_id: str
    channel_name: Optional[str]
    text: str
    ts: Optional[str]
    engagement_total: int
    views_count: int
    likes_count: int
    comments_count: int
    reactions_count: int


class TelegramResearchResponse(BaseModel):
    items: List[TelegramSnippet]


@router.post("/telegram/snippets", response_model=TelegramResearchResponse)
async def get_telegram_snippets_for_topic(
    request: Request,
    payload: TelegramResearchRequest,
    db: AsyncSession = Depends(get_db),
) -> TelegramResearchResponse:
    """
    Вернуть популярные Telegram‑посты пользователя по заданной теме.

    - Источник: parse_results + parse_tasks только этого user_id.
    - Фильтрация:
      - platform = telegram
      - content_text is not null
      - простое тематическое совпадение по ключевым словам темы
      - engagement (views/likes/comments/reactions) >= порогов
    - Сортировка: по engagement_total и дате по убыванию.
    """
    user_id = await get_user_id_from_request(request)

    topic = (payload.topic or "").strip().lower()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic must not be empty")

    # Простейшая эвристика извлечения ключевых слов из описания темы.
    # Берём только слова длиной > 3 символов, без дублей.
    import re

    words = re.findall(r"\b\w+\b", topic)
    keywords = list({w for w in words if len(w) > 3})[:8]  # ограничим до 8 ключевых слов

    # Базовый запрос по результатам этого пользователя и платформе Telegram.
    engagement_total = (
        ParseResult.likes_count
        + ParseResult.shares_count
        + ParseResult.comments_count
        + ParseResult.reactions_count
    )

    query = (
        select(ParseResult)
        .join(ParseTask, ParseResult.task_id == ParseTask.id)
        .where(
            ParseTask.user_id == user_id,
            ParseResult.platform == Platform.TELEGRAM,
            ParseResult.content_text.isnot(None),
        )
    )

    # Фильтр по просмотрам и engagement.
    if payload.min_views > 0:
        query = query.where(ParseResult.views_count >= payload.min_views)
    if payload.min_engagement > 0:
        query = query.where(engagement_total >= payload.min_engagement)

    # Тематический фильтр по ключевым словам (ILIKE по тексту и хэштегам).
    if keywords:
        like_clauses = []
        for kw in keywords:
            pattern = f"%{kw}%"
            like_clauses.append(ParseResult.content_text.ilike(pattern))
        query = query.where(or_(*like_clauses))

    # Сортируем по engagement и дате.
    query = (
        query.order_by(engagement_total.desc(), ParseResult.views_count.desc(), ParseResult.created_at.desc())
        .limit(payload.limit)
    )

    results = (await db.execute(query)).scalars().all()

    items: List[TelegramSnippet] = []
    for r in results:
        text = (r.content_text or "").strip()
        if not text:
            continue

        total_eng = int(
            (r.likes_count or 0)
            + (r.shares_count or 0)
            + (r.comments_count or 0)
            + (r.reactions_count or 0)
        )

        items.append(
            TelegramSnippet(
                source="telegram_post",
                channel_id=str(r.source_id),
                channel_name=r.source_name,
                text=text,
                ts=r.content_created_at.isoformat() if r.content_created_at else None,
                engagement_total=total_eng,
                views_count=int(r.views_count or 0),
                likes_count=int(r.likes_count or 0),
                comments_count=int(r.comments_count or 0),
                reactions_count=int(r.reactions_count or 0),
            )
        )

    return TelegramResearchResponse(items=items)

