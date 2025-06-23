#!/usr/bin/env python3
"""
Simple Celery worker without app dependencies.
"""

import os
import time
from celery import Celery

# Simple Redis broker setup  
redis_host = os.getenv('REDIS_HOST', 'redis')
redis_port = int(os.getenv('REDIS_PORT', '6379'))
broker_url = f'redis://{redis_host}:{redis_port}/0'

# Create simple Celery app
celery_app = Celery('parsing_worker', broker=broker_url)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    result_backend=broker_url
)

@celery_app.task(name="telegram_parse_channel")
def telegram_parse_channel(channel_username, user_id, **kwargs):
    """Simple Telegram channel parsing task."""
    print(f"Processing Telegram channel: {channel_username} for user {user_id}")
    
    # Simulate work
    time.sleep(2)
    
    result = {
        "channel": channel_username,
        "user_id": user_id, 
        "messages_parsed": 100,
        "status": "completed",
        "timestamp": time.time()
    }
    
    print(f"Completed Telegram channel: {channel_username}")
    return result

if __name__ == "__main__":
    print("Starting simple Telegram parsing worker...")
    
    # Start worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=1',
        '-Q', 'telegram_parsing',
        '-n', 'telegram_worker@%h'
    ]) 