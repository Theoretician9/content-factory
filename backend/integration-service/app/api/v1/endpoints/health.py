from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
from datetime import datetime

from ....database import get_async_session
from ....core.config import get_settings
from ....core.vault import IntegrationVaultClient

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/")
async def health_check():
    """Базовая проверка состояния сервиса"""
    return {
        "status": "healthy",
        "service": "integration-service",
        "timestamp": datetime.utcnow().isoformat(),
        "version": get_settings().VERSION
    }

@router.get("/detailed")
async def detailed_health_check(
    session: AsyncSession = Depends(get_async_session)
):
    """Детальная проверка состояния всех компонентов"""
    health_status = {
        "status": "healthy",
        "service": "integration-service",
        "timestamp": datetime.utcnow().isoformat(),
        "version": get_settings().VERSION,
        "components": {}
    }
    
    # Проверка базы данных
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar()
        health_status["components"]["database"] = {
            "status": "healthy",
            "type": "PostgreSQL"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "type": "PostgreSQL"
        }
        health_status["status"] = "degraded"
    
    # Проверка Vault
    try:
        vault_client = IntegrationVaultClient()
        # ✅ ИСПРАВЛЕНО: Проверяем правильный путь integration-service
        vault_client.get_secret('integration-service')
        health_status["components"]["vault"] = {
            "status": "healthy",
            "type": "HashiCorp Vault"
        }
    except Exception as e:
        logger.error(f"Vault health check failed: {e}")
        health_status["components"]["vault"] = {
            "status": "unhealthy",
            "error": str(e),
            "type": "HashiCorp Vault"
        }
        health_status["status"] = "degraded"
    
    # Если хотя бы один компонент нездоров, возвращаем 503
    if health_status["status"] != "healthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    
    return health_status

@router.get("/readiness")
async def readiness_check(
    session: AsyncSession = Depends(get_async_session)
):
    """Проверка готовности сервиса к обработке запросов"""
    try:
        # Проверяем подключение к базе данных
        await session.execute(text("SELECT 1"))
        
        return {
            "status": "ready",
            "service": "integration-service",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@router.get("/liveness")
async def liveness_check():
    """Проверка что сервис жив (для Kubernetes)"""
    return {
        "status": "alive",
        "service": "integration-service",
        "timestamp": datetime.utcnow().isoformat()
    } 