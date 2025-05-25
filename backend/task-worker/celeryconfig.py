from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

# Broker settings
broker_url = f'amqp://{os.getenv("RABBITMQ_USER", "user")}:{os.getenv("RABBITMQ_PASSWORD", "password")}@{os.getenv("RABBITMQ_HOST", "rabbitmq")}:5672//'
result_backend = f'redis://{os.getenv("REDIS_HOST", "redis")}:{os.getenv("REDIS_PORT", "6379")}/0'

# Task settings
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'UTC'
enable_utc = True

# Task execution settings
task_track_started = True
task_time_limit = 3600  # 1 hour
task_soft_time_limit = 3000  # 50 minutes

# Retry settings
task_acks_late = True
task_reject_on_worker_lost = True
task_default_retry_delay = 300  # 5 minutes
task_max_retries = 3
broker_connection_retry_on_startup = True

# Task priority
task_queue_max_priority = {
    'high_priority': 10,
    'default': 5,
    'low_priority': 1
}

# Worker settings
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 1000
worker_max_memory_per_child = 200000  # 200MB

# Beat schedule
beat_schedule = {
    'check-integration-health': {
        'task': 'check_integration_health',
        'schedule': 300.0,  # every 5 minutes
        'options': {'queue': 'low_priority'}
    },
    'cleanup-old-data': {
        'task': 'cleanup_data',
        'schedule': 3600.0,  # every hour
        'options': {'queue': 'low_priority'}
    }
}

# Queue settings
task_queues = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
        'queue_arguments': {'x-max-priority': 5}
    },
    'high_priority': {
        'exchange': 'high_priority',
        'routing_key': 'high_priority',
        'queue_arguments': {'x-max-priority': 10}
    },
    'low_priority': {
        'exchange': 'low_priority',
        'routing_key': 'low_priority',
        'queue_arguments': {'x-max-priority': 1}
    }
}

# Task routing
task_routes = {
    'sync_integration': {'queue': 'high_priority'},
    'send_notification': {'queue': 'high_priority'},
    'process_webhook': {'queue': 'high_priority'},
    'cleanup_data': {'queue': 'low_priority'},
    'check_integration_health': {'queue': 'low_priority'}
} 