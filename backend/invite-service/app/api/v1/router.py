"""
Основной роутер API v1 для Invite Service
"""

import importlib
from fastapi import APIRouter
from .endpoints import health, tasks, targets, execution, statistics

# Импорт модуля import (зарезервированное слово) через importlib
import_module = importlib.import_module('app.api.v1.endpoints.import')

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Invite Tasks"])
api_router.include_router(execution.router, prefix="/tasks", tags=["Task Execution"])
api_router.include_router(targets.router, prefix="/tasks", tags=["Target Management"])
api_router.include_router(statistics.router, tags=["Statistics & Reports"])
api_router.include_router(import_module.router, tags=["Data Import"]) 