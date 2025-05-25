from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

# Broker settings
broker_url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672//')
result_backend = os.getenv('REDIS_URL', 'redis://redis:6379/0')

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
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 1000

# Retry settings
task_acks_late = True
task_reject_on_worker_lost = True
task_default_retry_delay = 300  # 5 minutes
task_max_retries = 3

# Beat schedule for periodic tasks
beat_schedule = {
    'sync-integrations': {
        'task': 'sync_integration',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'args': (),
        'kwargs': {'force': True}
    },
    'cleanup-old-logs': {
        'task': 'cleanup_data',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
        'args': ('old_logs',),
        'kwargs': {'days': 30}
    },
    'cleanup-expired-tokens': {
        'task': 'cleanup_data',
        'schedule': crontab(hour='*/4'),  # Every 4 hours
        'args': ('expired_tokens',),
        'kwargs': {}
    },
    'check-integration-health': {
        'task': 'check_integration_health',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'args': (),
        'kwargs': {}
    }
}

# Queue settings
task_queues = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'high_priority': {
        'exchange': 'high_priority',
        'routing_key': 'high_priority',
    },
    'low_priority': {
        'exchange': 'low_priority',
        'routing_key': 'low_priority',
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