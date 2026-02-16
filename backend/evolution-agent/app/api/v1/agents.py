from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_user_id_from_request
from app.database import get_db_session
from app.models.calendar import CalendarSlot, CalendarSlotStatus
from app.models.post import Post
from app.models.strategy import Strategy
from app.services.orchestrator import Orchestrator
from app.services.persona_service import generate_persona_and_strategy


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


def _generate_default_persona_and_strategy_payload(
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

    # Persona/Strategy через Llama 3.1 8B (Groq); при ошибке — дефолтный payload
    strategy_data = await generate_persona_and_strategy(
        description=payload.description,
        tone=payload.tone or "friendly_expert",
        language=payload.language,
    )
    if strategy_data is None:
        strategy_data = _generate_default_persona_and_strategy_payload(payload)

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

    # Нормализуем from_dt/to_dt: приводим к UTC и убираем tzinfo,
    # т.к. в БД используется TIMESTAMP WITHOUT TIME ZONE (наивные даты).
    from_dt = payload.from_dt
    to_dt = payload.to_dt
    if from_dt.tzinfo is not None:
        from_dt = from_dt.astimezone(timezone.utc).replace(tzinfo=None)
    if to_dt.tzinfo is not None:
        to_dt = to_dt.astimezone(timezone.utc).replace(tzinfo=None)

    stmt = (
        select(CalendarSlot)
        .where(
            CalendarSlot.user_id == user_id,
            CalendarSlot.channel_id == payload.channel_id,
            CalendarSlot.dt >= from_dt,
            CalendarSlot.dt <= to_dt,
        )
        .order_by(CalendarSlot.dt.asc())
    )
    result = await db.execute(stmt)
    slots: List[CalendarSlot] = result.scalars().all()

    if not slots:
        raise HTTPException(status_code=404, detail="No slots in specified interval")

    # Пробрасываем текущий JWT в Orchestrator, чтобы он мог публиковать через integration-service
    auth_header = request.headers.get("Authorization")
    jwt_token: Optional[str] = None
    if auth_header and auth_header.lower().startswith("bearer "):
        jwt_token = auth_header.split(" ", 1)[1].strip()

    orchestrator = Orchestrator(db=db, jwt_token=jwt_token)

    # Пока запускаем генерацию слотов последовательно и синхронно
    for s in slots:
        if s.status == CalendarSlotStatus.PLANNED:
            await orchestrator.run_slot_generation(slot_id=str(s.id), user_id=user_id)

    # перечитываем статусы
    result_after = await db.execute(stmt)
    slots_after: List[CalendarSlot] = result_after.scalars().all()

    return {
        "channel_id": payload.channel_id,
        "slots": [
            {
                "slot_id": str(s.id),
                "dt": s.dt.isoformat(),
                "status": s.status,
            }
            for s in slots_after
        ],
        "message": "Force-run executed inline for matching slots.",
    }


class RegenerateRequest(BaseModel):
    feedback: Optional[str] = None


@router.post("/slots/{slot_id}/regenerate")
async def regenerate_slot(
    slot_id: str,
    request: Request,
    payload: RegenerateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Ручная регенерация поста для слота с пользовательским фидбеком.

    Алгоритм:
    - проверяем, что слот принадлежит пользователю;
    - удаляем старый пост для слота (если есть) и возвращаем слот в статус PLANNED;
    - запускаем Orchestrator.run_slot_generation с учётом feedback;
    - возвращаем обновлённый статус слота.
    """
    user_id = await get_user_id_from_request(request)

    # Находим слот пользователя
    stmt_slot = select(CalendarSlot).where(
        CalendarSlot.id == slot_id,
        CalendarSlot.user_id == user_id,
    )
    result = await db.execute(stmt_slot)
    slot: Optional[CalendarSlot] = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    # Удаляем существующий пост для слота (при наличии), чтобы не нарушить уникальность slot_id
    stmt_post = select(Post).where(Post.slot_id == slot.id)
    post_result = await db.execute(stmt_post)
    existing_post: Optional[Post] = post_result.scalar_one_or_none()
    if existing_post:
        await db.delete(existing_post)
        await db.commit()

    # Возвращаем слот в статус PLANNED для повторной генерации
    slot.status = CalendarSlotStatus.PLANNED
    slot.updated_at = datetime.utcnow()
    await db.commit()

    # Пробрасываем JWT в Orchestrator
    auth_header = request.headers.get("Authorization")
    jwt_token: Optional[str] = None
    if auth_header and auth_header.lower().startswith("bearer "):
        jwt_token = auth_header.split(" ", 1)[1].strip()

    orchestrator = Orchestrator(db=db, jwt_token=jwt_token)
    await orchestrator.run_slot_generation(slot_id=str(slot.id), user_id=user_id, feedback=payload.feedback)

    # перечитываем слот после генерации
    result_after = await db.execute(stmt_slot)
    slot_after: Optional[CalendarSlot] = result_after.scalar_one_or_none()

    if not slot_after:
        raise HTTPException(status_code=404, detail="Slot not found after regeneration")

    return {
        "slot_id": str(slot_after.id),
        "dt": slot_after.dt.isoformat(),
        "status": slot_after.status,
    }

