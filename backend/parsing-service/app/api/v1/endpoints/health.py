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
    """Get service health status."""
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
