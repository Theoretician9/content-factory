"""
Конфигурация Celery для Invite Service
"""

import os
from celery import Celery
from kombu import Queue

# Конфигурация Celery
celery_app = Celery(
    'invite-service',
    broker=os.getenv('CELERY_BROKER_URL', 'pyamqp://guest@rabbitmq:5672//'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
    include=[
        'workers.invite_worker',
        'workers.maintenance_worker'
    ]
)

# Конфигурация Celery
celery_app.conf.update(
    # Часовой пояс
    timezone='UTC',
    enable_utc=True,
    
    # Сериализация
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Результаты
    result_expires=3600,  # Результаты хранятся 1 час
    
    # Routing и очереди
    task_routes={
        'workers.invite_worker.execute_invite_task': {'queue': 'invite-high'},
        'workers.invite_worker.process_target_batch': {'queue': 'invite-normal'},
        'workers.invite_worker.single_invite_operation': {'queue': 'invite-normal'},
        'workers.maintenance_worker.cleanup_expired_tasks': {'queue': 'invite-low'},
        'workers.maintenance_worker.update_rate_limits': {'queue': 'invite-low'},
    },
    
    # Определение очередей
    task_queues=(
        Queue('invite-high', routing_key='invite-high'),
        Queue('invite-normal', routing_key='invite-normal'),
        Queue('invite-low', routing_key='invite-low'),
    ),
    
    # Настройки воркеров
    worker_prefetch_multiplier=1,  # Один таск на воркер
    task_acks_late=True,           # Подтверждение после завершения
    worker_disable_rate_limits=False,
    
    # Мониторинг
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Лимиты времени выполнения
    task_time_limit=30 * 60,       # 30 минут hard limit
    task_soft_time_limit=25 * 60,  # 25 минут soft limit
    
    # Retry настройки
    task_default_retry_delay=60,   # 1 минута по умолчанию
    task_max_retries=3,
    
    # Beat schedule для периодических задач
    beat_schedule={
        'cleanup-expired-tasks': {
            'task': 'workers.maintenance_worker.cleanup_expired_tasks',
            'schedule': 300.0,  # Каждые 5 минут
        },
        'update-rate-limits': {
            'task': 'workers.maintenance_worker.update_rate_limits',
            'schedule': 60.0,   # Каждую минуту
        },
    },
)

# Логирование
import logging
logging.basicConfig(level=logging.INFO)

# Экспорт приложения
__all__ = ['celery_app'] 