#!/usr/bin/env python3
"""
Simple Celery worker entry point.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, '/app')

if __name__ == "__main__":
    from app.workers.celery_app import celery_app
    
    # Simple worker start
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=1',
        '-Q', 'telegram_parsing'
    ]) 