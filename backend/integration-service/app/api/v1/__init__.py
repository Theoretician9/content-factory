from fastapi import APIRouter
from .endpoints import telegram, health

api_router = APIRouter()

# Включаем роутеры  
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(health.router, prefix="/health", tags=["health"]) 