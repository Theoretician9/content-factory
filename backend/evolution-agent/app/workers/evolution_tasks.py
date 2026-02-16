"""
Celery таски для evolution-agent.

- schedule_due_slots: периодически находит слоты, которым пора запускаться, и
  ставит задачи генерации в очередь.
- run_slot_generation_task: обёртка над Orchestrator.run_slot_generation.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import select

from app.database import get_session_factory
from app.models.calendar import CalendarSlot, CalendarSlotStatus
from app.services.orchestrator import Orchestrator


logger = logging.getLogger(__name__)


@shared_task(name="evolution_agent.run_slot_generation_task", bind=True, max_retries=3)
def run_slot_generation_task(self, slot_id: str, user_id: int, feedback: Optional[str] = None) -> None:
    """
    Celery‑таска: запустить пайплайн генерации для одного слота.

    Выполняет ту же логику, что и Orchestrator.run_slot_generation, но в фоновом воркере.
    """

    async def _run():
        session_factory = get_session_factory()
        async with session_factory() as session:
            orchestrator = Orchestrator(db=session)
            await orchestrator.run_slot_generation(slot_id=slot_id, user_id=user_id, feedback=feedback)

    import asyncio

    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("❌ Celery run_slot_generation_task error: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=min(60 * (self.request.retries + 1), 600))


@shared_task(name="evolution_agent.schedule_due_slots")
def schedule_due_slots() -> None:
    """
    Периодическая таска: ищет слоты в статусе PLANNED, у которых dt <= сейчас,
    и ставит их в очередь на генерацию.
    """

    async def _schedule():
        session_factory = get_session_factory()
        async with session_factory() as session:
            now = datetime.utcnow()
            # Небольшое окно вперёд, чтобы не пропускать ближайшие слоты
            window_to = now + timedelta(minutes=5)

            stmt = (
                select(CalendarSlot)
                .where(
                    CalendarSlot.status == CalendarSlotStatus.PLANNED,
                    CalendarSlot.dt <= window_to,
                )
                .order_by(CalendarSlot.dt.asc())
            )
            result = await session.execute(stmt)
            slots = result.scalars().all()

            from app.workers.celery_app import celery_app

            for slot in slots:
                logger.info(
                    "📅 Scheduling slot generation via Celery: slot_id=%s, user_id=%s, dt=%s",
                    slot.id,
                    slot.user_id,
                    slot.dt,
                )
                celery_app.send_task(
                    "evolution_agent.run_slot_generation_task",
                    args=[str(slot.id), slot.user_id, None],
                )

    import asyncio

    try:
        asyncio.run(_schedule())
    except Exception as exc:  # noqa: BLE001
        logger.error("❌ Celery schedule_due_slots error: %s", exc, exc_info=True)

