from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from app.core.auth import get_user_id_from_request
from app.database import get_db_session
from app.models.calendar import CalendarSlot, CalendarSlotStatus
from app.models.post import Post
from app.models.strategy import Strategy
from app.models.memory import MemoryLog
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
    channel_id: str


class OnboardResponse(BaseModel):
    strategy_id: str
    channel_id: str
    slots: List[CalendarSlotOut]


def _normalize_channel_id_value(raw: str) -> str:
    """
    Нормализует channel_id:
    - убирает префиксы t.me/ и протоколы;
    - убирает ведущий @;
    - тримминг пробелов.
    """
    if raw is None:
        return ""
    ch = str(raw).strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if ch.startswith(prefix):
            ch = ch[len(prefix) :]
    ch = ch.lstrip("@").strip()
    return ch


@OnboardRequest.model_validator(mode="after")
def _normalize_channel_id(cls, values: "OnboardRequest") -> "OnboardRequest":  # type: ignore[override]
    values.channel_id = _normalize_channel_id_value(values.channel_id)
    return values


def _generate_default_persona_and_strategy_payload(
    req: OnboardRequest,
) -> dict:
    """Простейшая нормализация запроса и генерация persona/content_mix/schedule."""
    persona = {
        "tone": req.tone or "friendly_expert",
        "language": req.language,
        "forbidden_topics": [],
        # Сохраняем исходное описание канала, чтобы использовать его при генерации постов
        "channel_description": req.description,
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

    # Деактивируем только активные стратегии для этого канала (is_active = True),
    # чтобы не трогать уже неактивные версии.
    await db.execute(
        Strategy.__table__.update()
        .where(
            Strategy.user_id == user_id,
            Strategy.channel_id == payload.channel_id,
            Strategy.is_active.is_(True),
        )
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
                channel_id=s.channel_id,
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
        raw = channel_id
        norm = _normalize_channel_id_value(channel_id)
        if norm != raw:
            stmt = stmt.where(CalendarSlot.channel_id.in_([raw, norm]))
        else:
            stmt = stmt.where(CalendarSlot.channel_id == norm)
    stmt = stmt.order_by(CalendarSlot.dt.asc())

    result = await db.execute(stmt)
    slots: List[CalendarSlot] = result.scalars().all()

    return [
        CalendarSlotOut(
            slot_id=str(s.id),
            dt=s.dt,
            pillar=s.pillar,
            status=s.status,
            channel_id=s.channel_id,
        )
        for s in slots
    ]


class ChannelStatsOut(BaseModel):
    total_slots: int
    planned: int
    processing: int
    ready: int
    published: int
    failed: int
    total_posts: int
    total_memory_logs: int
    last_published_at: Optional[datetime] = None


class ChannelSummaryOut(BaseModel):
    channel_id: str
    description: Optional[str] = None
    persona: Optional[Dict] = None
    content_mix: Optional[Dict] = None
    schedule_rules: Optional[Dict] = None
    stats: ChannelStatsOut


@router.get("/channels/{channel_id}/summary", response_model=ChannelSummaryOut)
async def get_channel_summary(
    channel_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> ChannelSummaryOut:
    """
    Краткое описание канала и стратегии + статистика по слотам/постам.
    """
    user_id = await get_user_id_from_request(request)

    raw_channel = channel_id
    norm_channel = _normalize_channel_id_value(channel_id)

    # Берём последнюю стратегию по этому каналу (не только is_active, чтобы всегда была сводка)
    stmt_strategy = (
        select(Strategy)
        .where(
            Strategy.user_id == user_id,
            Strategy.channel_id.in_(
                [raw_channel, norm_channel] if norm_channel != raw_channel else [norm_channel]
            ),
        )
        .order_by(Strategy.version.desc())
    )
    res_strategy = await db.execute(stmt_strategy)
    strategy: Optional[Strategy] = res_strategy.scalars().first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Стратегия для канала не найдена")

    persona = strategy.persona_json or {}
    content_mix = strategy.content_mix_json or {}
    schedule_rules = strategy.schedule_rules_json or {}
    description = None
    if isinstance(persona, dict):
        description = persona.get("channel_description") or persona.get("description")

    # Слоты по этому каналу
    stmt_slots = select(CalendarSlot).where(
        CalendarSlot.user_id == user_id,
        CalendarSlot.channel_id.in_(
            [raw_channel, norm_channel] if norm_channel != raw_channel else [norm_channel]
        ),
    )
    res_slots = await db.execute(stmt_slots)
    slots: List[CalendarSlot] = res_slots.scalars().all()

    status_counts: Dict[str, int] = {}
    for s in slots:
        key = (s.status or "").lower()
        status_counts[key] = status_counts.get(key, 0) + 1

    # Кол-во постов и логов, последнее время публикации
    posts_count_q = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == user_id,
            Post.channel_id.in_(
                [raw_channel, norm_channel] if norm_channel != raw_channel else [norm_channel]
            ),
        )
    )
    total_posts = int(posts_count_q.scalar() or 0)

    logs_count_q = await db.execute(
        select(func.count(MemoryLog.id)).where(
            MemoryLog.user_id == user_id,
            MemoryLog.channel_id.in_(
                [raw_channel, norm_channel] if norm_channel != raw_channel else [norm_channel]
            ),
        )
    )
    total_logs = int(logs_count_q.scalar() or 0)

    last_published_q = await db.execute(
        select(func.max(Post.created_at)).where(
            Post.user_id == user_id,
            Post.channel_id.in_(
                [raw_channel, norm_channel] if norm_channel != raw_channel else [norm_channel]
            ),
            Post.telegram_message_id.isnot(None),
        )
    )
    last_published_at = last_published_q.scalar()

    stats = ChannelStatsOut(
        total_slots=len(slots),
        planned=status_counts.get("planned", 0),
        processing=status_counts.get("processing", 0),
        ready=status_counts.get("ready", 0),
        published=status_counts.get("published", 0),
        failed=status_counts.get("failed", 0),
        total_posts=total_posts,
        total_memory_logs=total_logs,
        last_published_at=last_published_at,
    )

    return ChannelSummaryOut(
        channel_id=norm_channel or raw_channel,
        description=description,
        persona=persona,
        content_mix=content_mix,
        schedule_rules=schedule_rules,
        stats=stats,
    )


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Полное удаление канала для текущего пользователя:
    - все слоты, посты, memory_logs;
    - все стратегии по этому каналу.
    Выполняется через явные DELETE, чтобы избежать попыток ORM проставить NULL в strategy_id.
    """
    user_id = await get_user_id_from_request(request)

    # Проверяем, что для канала вообще есть стратегии (и, следовательно, данные)
    has_strategy_q = await db.execute(
        select(func.count(Strategy.id)).where(
            Strategy.user_id == user_id,
            Strategy.channel_id == channel_id,
        )
    )
    if int(has_strategy_q.scalar() or 0) == 0:
        raise HTTPException(status_code=404, detail="Канал не найден или уже удалён")

    # Удаляем в безопасном порядке: сначала логи, затем посты, слоты, стратегии.
    await db.execute(
        delete(MemoryLog).where(
            MemoryLog.user_id == user_id,
            MemoryLog.channel_id == channel_id,
        )
    )

    await db.execute(
        delete(Post).where(
            Post.user_id == user_id,
            Post.channel_id == channel_id,
        )
    )

    await db.execute(
        delete(CalendarSlot).where(
            CalendarSlot.user_id == user_id,
            CalendarSlot.channel_id == channel_id,
        )
    )

    await db.execute(
        delete(Strategy).where(
            Strategy.user_id == user_id,
            Strategy.channel_id == channel_id,
        )
    )

    await db.commit()

    return {"status": "deleted", "channel_id": channel_id}


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

    # Определяем таймзону пользователя/канала из активной стратегии
    tzinfo = timezone.utc
    stmt_strategy = (
        select(Strategy)
        .where(
            Strategy.user_id == user_id,
            Strategy.channel_id == payload.channel_id,
            Strategy.is_active.is_(True),
        )
        .order_by(Strategy.version.desc())
    )
    strategy_result = await db.execute(stmt_strategy)
    strategy: Optional[Strategy] = strategy_result.scalars().first()
    if strategy:
        rules = strategy.schedule_rules_json or {}
        tz_name = rules.get("timezone") or "UTC"
        try:
            tzinfo = ZoneInfo(tz_name)
        except Exception:
            tzinfo = timezone.utc

    # Нормализуем from_dt/to_dt: приводим к локальной таймзоне пользователя и далее в UTC,
    # затем убираем tzinfo, т.к. в БД TIMESTAMP WITHOUT TIME ZONE.
    def _normalize(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tzinfo)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    from_dt = _normalize(payload.from_dt)
    to_dt = _normalize(payload.to_dt)

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


@router.post("/slots/{slot_id}/publish-now")
async def publish_slot_now(
    slot_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Принудительная генерация и публикация поста для указанного слота.

    Используется для кнопки «Опубликовать сейчас» рядом с плановыми слотами.
    """
    user_id = await get_user_id_from_request(request)

    # Проверяем, что слот принадлежит пользователю
    stmt_slot = select(CalendarSlot).where(
        CalendarSlot.id == slot_id,
        CalendarSlot.user_id == user_id,
    )
    result = await db.execute(stmt_slot)
    slot: Optional[CalendarSlot] = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    if slot.status != CalendarSlotStatus.PLANNED:
        raise HTTPException(
            status_code=400,
            detail=f"Slot status must be PLANNED to publish now, got {slot.status}",
        )

    # Пробрасываем JWT в Orchestrator
    auth_header = request.headers.get("Authorization")
    jwt_token: Optional[str] = None
    if auth_header and auth_header.lower().startswith("bearer "):
        jwt_token = auth_header.split(" ", 1)[1].strip()

    orchestrator = Orchestrator(db=db, jwt_token=jwt_token)
    # Генерация + публикация (если JWT передан)
    await orchestrator.run_slot_generation(slot_id=str(slot.id), user_id=user_id)

    # перечитываем слот после выполнения пайплайна
    result_after = await db.execute(stmt_slot)
    slot_after: Optional[CalendarSlot] = result_after.scalar_one_or_none()

    if not slot_after:
        raise HTTPException(status_code=404, detail="Slot not found after publish-now")

    # Если пайплайн завершился с ошибкой (например, лимиты LLM / публикации),
    # явно возвращаем 5xx, чтобы фронт мог показать понятное сообщение.
    if slot_after.status == CalendarSlotStatus.FAILED:
        raise HTTPException(
            status_code=502,
            detail="Не удалось сгенерировать или опубликовать пост для слота. "
            "Проверь лимиты LLM/публикации и логи evolution-agent.",
        )

    return {
        "slot_id": str(slot_after.id),
        "dt": slot_after.dt.isoformat(),
        "status": slot_after.status,
    }

