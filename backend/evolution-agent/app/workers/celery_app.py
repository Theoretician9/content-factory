"""
Celery конфигурация для evolution-agent.

Используется для планового запуска генерации слотов (ежедневный контент‑цикл).
"""
import logging
from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings


logger = logging.getLogger(__name__)

settings = get_settings()


celery_app = Celery(
    "evolution_agent_workers",
    broker=f"redis://redis:6379/0",
    backend=f"redis://redis:6379/0",
    include=["app.workers.evolution_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Базовый пример расписания:
# - каждые 5 минут проверяем слоты, которым пора запускаться, и ставим таски в очередь.
celery_app.conf.beat_schedule = {
    "schedule-slot-generation": {
        "task": "evolution_agent.schedule_due_slots",
        "schedule": 300.0,  # каждые 5 минут
    },
}

__all__ = ["celery_app"]

