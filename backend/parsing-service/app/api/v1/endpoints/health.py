"""Health check endpoints."""

from fastapi import APIRouter
from ....core.config import settings
from ....schemas.base import HealthResponse

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Get service health status."""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        platform_support=settings.SUPPORTED_PLATFORMS,
        details={
            "app_name": settings.APP_NAME,
            "supported_platforms": [p.value for p in settings.SUPPORTED_PLATFORMS]
        }
    ) 