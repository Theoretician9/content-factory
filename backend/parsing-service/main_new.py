"""
Main FastAPI application for Multi-Platform Parser Service.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.auth import get_current_user_id
from app.schemas.base import HealthResponse

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"🔧 Debug mode: {settings.DEBUG}")
    logger.info(f"📱 Supported platforms: {[p.value for p in settings.SUPPORTED_PLATFORMS]}")
    
    # TODO: Initialize database connection
    # TODO: Initialize Vault connection
    # TODO: Initialize Redis connection
    # TODO: Initialize RabbitMQ connection
    
    yield
    
    logger.info("🛑 Shutting down Multi-Platform Parser Service")
    # TODO: Cleanup connections


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Universal parsing service for social media platforms (Telegram, Instagram, WhatsApp, etc.)",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Get service health status."""
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


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "supported_platforms": [p.value for p in settings.SUPPORTED_PLATFORMS],
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production"
    }


# TODO: Include API routers
# from app.api.v1.router import router as v1_router
# app.include_router(v1_router)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An internal server error occurred",
            "details": str(exc) if settings.DEBUG else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_new:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 