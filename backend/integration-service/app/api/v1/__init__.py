from fastapi import APIRouter
from .endpoints import telegram, health
# Временно убрал telegram_invites до исправления проблем с импортами

api_router = APIRouter()

# Включаем роутеры  
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
# api_router.include_router(telegram_invites.router, prefix="/telegram/invites", tags=["telegram-invites"])
api_router.include_router(health.router, prefix="/health", tags=["health"]) 