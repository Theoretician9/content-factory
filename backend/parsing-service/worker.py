#!/usr/bin/env python3
"""
Entry point for Celery worker.
"""

import os
import sys

# Add app to Python path
sys.path.insert(0, '/app')

# Set environment
os.environ.setdefault('PYTHONPATH', '/app')

if __name__ == '__main__':
    from app.workers.celery_app import celery_app
    
    # Start Celery worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '-Q', 'telegram_parsing',
        '-n', 'telegram_worker@%h'
    ]) 