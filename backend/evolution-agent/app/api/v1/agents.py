from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_user_id_from_request
from app.database import get_db_session
from app.models.calendar import CalendarSlot, CalendarSlotStatus
from app.models.strategy import Strategy


router = APIRouter()


class OnboardRequest(BaseModel):
    channel_id: str
    description: str
    tone: Optional[str] = None
    language: str = "ru"


class CalendarSlotOut(BaseModel):
    slot_id: str
    dt: datetime
    pillar: Optional[str] = None
    status: str


class OnboardResponse(BaseModel):
    strategy_id: str
    channel_id: str
    slots: List[CalendarSlotOut]


async def _generate_default_persona_and_strategy_payload(
    req: OnboardRequest,
) -> dict:
    """Простейшая нормализация запроса и генерация persona/content_mix/schedule."""
    persona = {
        "tone": req.tone or "friendly_expert",
        "language": req.language,
        "forbidden_topics": [],
    }
    content_mix = {
        "education": 0.5,
        "opinion": 0.3,
        "news": 0.2,
    }
    schedule_rules = {
        "posts_per_day": 1,
        "preferred_hours": [11],
        "timezone": "UTC",
    }
    return {
        "persona_json": persona,
        "content_mix_json": content_mix,
        "schedule_rules_json": schedule_rules,
    }


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_agent(
    request: Request,
    payload: OnboardRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Инициализация агента для пользователя и канала.

    MVP‑реализация:
    - создаёт простую стратегию (версия 1);
    - генерирует 7 ежедневных слотов вперёд;
    - возвращает стратегию и календарь.
    """
    user_id = await get_user_id_from_request(request)

    strategy_data = await _generate_default_persona_and_strategy_payload(payload)

    # Деактивируем предыдущие стратегии для этого канала
    await db.execute(
        Strategy.__table__.update()
        .where(Strategy.user_id == user_id, Strategy.channel_id == payload.channel_id)
        .values(is_active=False)
    )

    strategy = Strategy(
        user_id=user_id,
        channel_id=payload.channel_id,
        version=1,
        **strategy_data,
    )
    db.add(strategy)
    await db.flush()

    now = datetime.utcnow()
    slots: List[CalendarSlot] = []
    for i in range(7):
        slot_dt = now + timedelta(days=i, hours=1)
        slot = CalendarSlot(
            user_id=user_id,
            channel_id=payload.channel_id,
            strategy_id=strategy.id,
            dt=slot_dt,
            status=CalendarSlotStatus.PLANNED,
            pillar=None,
        )
        db.add(slot)
        slots.append(slot)

    await db.commit()

    return OnboardResponse(
        strategy_id=str(strategy.id),
        channel_id=payload.channel_id,
        slots=[
            CalendarSlotOut(
                slot_id=str(s.id),
                dt=s.dt,
                pillar=s.pillar,
                status=s.status,
            )
            for s in slots
        ],
    )


@router.get("/calendar", response_model=List[CalendarSlotOut])
async def get_calendar(
    request: Request,
    channel_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Получить текущий контент‑план пользователя.
    """
    user_id = await get_user_id_from_request(request)

    stmt = select(CalendarSlot).where(CalendarSlot.user_id == user_id)
    if channel_id:
        stmt = stmt.where(CalendarSlot.channel_id == channel_id)
    stmt = stmt.order_by(CalendarSlot.dt.asc())

    result = await db.execute(stmt)
    slots: List[CalendarSlot] = result.scalars().all()

    return [
        CalendarSlotOut(
            slot_id=str(s.id),
            dt=s.dt,
            pillar=s.pillar,
            status=s.status,
        )
        for s in slots
    ]


class ForceRunRequest(BaseModel):
    channel_id: str
    from_dt: datetime
    to_dt: datetime


@router.post("/force-run")
async def force_run(
    request: Request,
    payload: ForceRunRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Принудительный запуск пайплайна для набора слотов (пока без Celery).

    Пока что это заглушка: она только возвращает список слотов в интервале.
    В следующих шагах сюда будет интегрирован оркестратор и Celery‑таски.
    """
    user_id = await get_user_id_from_request(request)

    stmt = (
        select(CalendarSlot)
        .where(
            CalendarSlot.user_id == user_id,
            CalendarSlot.channel_id == payload.channel_id,
            CalendarSlot.dt >= payload.from_dt,
            CalendarSlot.dt <= payload.to_dt,
        )
        .order_by(CalendarSlot.dt.asc())
    )
    result = await db.execute(stmt)
    slots: List[CalendarSlot] = result.scalars().all()

    if not slots:
        raise HTTPException(status_code=404, detail="No slots in specified interval")

    return {
        "channel_id": payload.channel_id,
        "slots": [
            {
                "slot_id": str(s.id),
                "dt": s.dt.isoformat(),
                "status": s.status,
            }
            for s in slots
        ],
        "message": "Force-run registered (actual generation pipeline will be wired next).",
    }

