"""Celery app configuration."""

from celery import Celery
from ..core.config import settings

# Create Celery instance (renamed to 'app' for docker-compose compatibility)
app = Celery(
    "parsing_service",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    include=[
        "app.workers.telegram_worker",
        "app.workers.parsing_worker"
    ]
)

# Celery configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    task_routes={
        "app.workers.telegram_worker.*": {"queue": "telegram_queue"},
        "app.workers.parsing_worker.*": {"queue": "general_queue"},
    },
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
)

# Queue definitions (синхронизировано с docker-compose.yml)
app.conf.task_routes = {
    "telegram_parse_channel": {"queue": "telegram_queue"},
    "telegram_parse_group": {"queue": "telegram_queue"},
    "telegram_search_communities": {"queue": "telegram_queue"},
    "general_parse_task": {"queue": "general_queue"},
}

if __name__ == "__main__":
    app.start()

# Backward compatibility
celery_app = app
