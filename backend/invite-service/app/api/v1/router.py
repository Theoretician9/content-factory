"""
Основной роутер API v1 для Invite Service
"""

from fastapi import APIRouter
from .endpoints import health, tasks, targets

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Invite Tasks"])
api_router.include_router(targets.router, prefix="/tasks", tags=["Target Management"]) 