#!/usr/bin/env python3
"""Celery worker entry point."""

import os
import sys
from app.workers.celery_app import celery_app

if __name__ == "__main__":
    # Start Celery worker
    celery_app.start() 