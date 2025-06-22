"""
Health check endpoints for parsing service.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ....core.config import settings
from ....schemas.base import HealthResponse

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Get service health status.
    
    Returns basic information about the service status,
    version, and supported platforms.
    """
    try:
        return HealthResponse(
            status="healthy",
            version=settings.VERSION,
            platform_support=settings.SUPPORTED_PLATFORMS,
            details={
                "app_name": settings.APP_NAME,
                "debug": settings.DEBUG,
                "supported_platforms": [p.value for p in settings.SUPPORTED_PLATFORMS]
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check():
    """
    Get detailed health status including external dependencies.
    """
    try:
        health_details = {
            "status": "healthy",
            "version": settings.VERSION,
            "database": {"status": "unknown"},  # TODO: Check database connection
            "vault": {"status": "unknown"},     # TODO: Check Vault connection
            "redis": {"status": "unknown"},     # TODO: Check Redis connection
            "rabbitmq": {"status": "unknown"}   # TODO: Check RabbitMQ connection
        }
        
        return health_details
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Detailed health check failed: {str(e)}"
        ) 