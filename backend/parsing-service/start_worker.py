#!/usr/bin/env python3
"""Celery worker startup script."""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, '/app')

# Import and start celery app
from app.workers.celery_app import celery_app

if __name__ == "__main__":
    # Get worker type from environment
    worker_type = os.getenv('CELERY_WORKER_TYPE', 'telegram')
    queue = f"{worker_type}_parsing"
    worker_name = f"{worker_type}_worker@%h"
    
    # Start worker
    celery_app.worker_main([
        'worker',
        '-Q', queue,
        '-n', worker_name,
        '--loglevel=info',
        '--concurrency=2'
    ]) 