"""
Health check endpoints для Invite Service
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def health_check():
    """Базовый health check сервиса"""
    return {
        "status": "healthy",
        "service": "invite-service",
        "version": "1.0.0"
    }


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Детальный health check с проверкой компонентов"""
    health_data = {
        "status": "healthy",
        "service": "invite-service",
        "version": "1.0.0",
        "components": {}
    }
    
    # Проверка базы данных
    try:
        db.execute(text("SELECT 1"))
        health_data["components"]["database"] = {"status": "healthy"}
    except Exception as e:
        health_data["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_data["status"] = "unhealthy"
    
    # TODO: Добавить проверки Redis, Integration Service и других компонентов
    
    return health_data 