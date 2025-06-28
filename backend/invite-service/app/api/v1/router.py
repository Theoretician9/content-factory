"""
Основной роутер API v1 для Invite Service
"""

from fastapi import APIRouter

from .endpoints import health, tasks

# Создание основного роутера для API v1
api_router = APIRouter()

# Подключение всех endpoint роутеров
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Invite Tasks"]) 