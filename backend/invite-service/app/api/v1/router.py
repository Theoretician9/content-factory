"""
Основной роутер API v1 для Invite Service
"""

from fastapi import APIRouter
from .endpoints import health, tasks, targets, execution

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Invite Tasks"])
api_router.include_router(execution.router, prefix="/tasks", tags=["Task Execution"])
api_router.include_router(targets.router, prefix="/tasks", tags=["Target Management"]) 