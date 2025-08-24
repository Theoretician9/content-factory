from fastapi import APIRouter
from .endpoints import telegram, health, telegram_invites, account_manager

api_router = APIRouter()

# Включаем роутеры  
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(telegram_invites.router, prefix="/telegram/invites", tags=["telegram-invites"])
api_router.include_router(account_manager.router, prefix="/account-manager", tags=["account-manager"])
api_router.include_router(health.router, prefix="/health", tags=["health"]) 