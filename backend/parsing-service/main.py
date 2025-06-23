"""
Main FastAPI application for Multi-Platform Parser Service.

Updated to support multi-platform parsing architecture while maintaining
backward compatibility with existing parsing functionality.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# New multi-platform imports
from app.core.config import settings
# Temporarily disable metrics to fix CollectorRegistry duplication error
# from app.core.metrics import start_metrics_server, get_metrics_collector
from app.database import init_database
from app.schemas.base import HealthResponse

# API routers
# Temporarily disable external routers due to null bytes issue
# from app.api.v1.endpoints.health import router as health_router

# Legacy imports (keep for compatibility)
import uvicorn
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import json
import os
from datetime import datetime
import asyncio
import pandas as pd
import aiohttp
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import redis
from celery import Celery
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import time
import random

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
    
    # Initialize database
    db_initialized = await init_database()
    if not db_initialized:
        logger.error("❌ Failed to initialize database")
    
    # Start metrics server
    # metrics_started = start_metrics_server()  # Временно отключено
    # if metrics_started:
    #     logger.info(f"📊 Metrics available at http://localhost:{settings.METRICS_PORT}")
    
    # Initialize metrics
    # metrics = get_metrics_collector()  # Временно отключено
    
    yield
    
    logger.info("🛑 Shutting down Multi-Platform Parser Service")


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


# Health check endpoint for multi-platform architecture
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
            "supported_platforms": [p.value for p in settings.SUPPORTED_PLATFORMS],
            "legacy_support": True  # Indicates legacy endpoints still work
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
        "architecture": "multi-platform",
        "supported_platforms": [p.value for p in settings.SUPPORTED_PLATFORMS],
        "api": {
            "health": "/health",
            "v1": "/v1/",
            "docs": "/docs" if settings.DEBUG else "disabled"
        },
        "legacy_endpoints": {
            "parse": "/parse",
            "stats": "/stats"
        },
        "monitoring": {
            "metrics": f"http://localhost:{settings.METRICS_PORT}" if settings.PROMETHEUS_METRICS_ENABLED else "disabled"
        }
    }


# Include new API routers
# app.include_router(health_router, prefix="/v1/health", tags=["Health"])

# Include other routers
# Temporarily disable external routers due to null bytes issue
# from app.api.v1.endpoints.tasks import router as tasks_router
# from app.api.v1.endpoints.results import router as results_router
# app.include_router(tasks_router, prefix="/v1/tasks", tags=["Parse Tasks"])
# app.include_router(results_router, prefix="/v1/results", tags=["Parse Results"])


# =============================================================================
# LEGACY ENDPOINTS (preserved for backward compatibility)
# =============================================================================

# Legacy database and models (preserved)
DATABASE_URL = "mysql+pymysql://parsing_user:parsing_password@localhost/parsing_db"
Base = declarative_base()

class ParsedData(Base):
    __tablename__ = "parsed_data"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False)
    title = Column(String(200))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    data_type = Column(String(50))  # 'web', 'api', 'file'
    status = Column(String(20), default='completed')
    parse_metadata = Column(JSON)

# Legacy Redis and Celery (preserved)
redis_client = redis.Redis(host='localhost', port=6379, db=0)
celery_app = Celery('parsing_service', broker='redis://localhost:6379/0')

# Legacy schemas (preserved)
class ParseRequest(BaseModel):
    source_type: str  # 'web', 'api', 'file'
    source: str
    parameters: Dict[str, Any] = {}
    data_type: str = "text"
    
class ParseResponse(BaseModel):
    task_id: str
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    
# Legacy endpoints (preserved)
@app.post("/parse", response_model=ParseResponse, tags=["Legacy"])
async def parse_data(request: ParseRequest):
    """Legacy parsing endpoint - preserved for backward compatibility."""
    logger.info(f"📊 Legacy parse request: {request.source_type}")
    
    try:
        task_id = f"legacy_{int(time.time())}"
        
        if request.source_type == "web":
            # Legacy web parsing
            result = await parse_web_legacy(request.source, request.parameters)
        elif request.source_type == "api":
            # Legacy API parsing  
            result = await parse_api_legacy(request.source, request.parameters)
        elif request.source_type == "file":
            # Legacy file parsing
            result = await parse_file_legacy(request.source, request.parameters)
        else:
            raise ValueError("Unsupported source type")
            
        return ParseResponse(
            task_id=task_id,
            status="completed",
            message="Parsed successfully (legacy mode)",
            data=result
        )
        
    except Exception as e:
        logger.error(f"❌ Legacy parsing failed: {e}")
        return ParseResponse(
            task_id="",
            status="failed", 
            message=f"Parsing failed: {str(e)}"
        )

# Legacy parsing functions (preserved)
async def parse_web_legacy(url: str, parameters: Dict) -> Dict:
    """Legacy web parsing."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            return {
                "title": soup.title.string if soup.title else "",
                "text": soup.get_text()[:1000],
                "links": [a.get('href') for a in soup.find_all('a', href=True)][:10],
                "images": [img.get('src') for img in soup.find_all('img', src=True)][:5]
            }

async def parse_api_legacy(endpoint: str, parameters: Dict) -> Dict:
    """Legacy API parsing."""
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint, params=parameters) as response:
            data = await response.json()
            return {"api_data": data}

async def parse_file_legacy(file_path: str, parameters: Dict) -> Dict:
    """Legacy file parsing."""
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
        return {"rows": len(df), "columns": list(df.columns), "sample": df.head().to_dict()}
    else:
        return {"error": "Unsupported file format"}

@app.get("/parse/{task_id}", tags=["Legacy"])
async def get_parse_result_legacy(task_id: str):
    """Get legacy parsing result."""
    return {"task_id": task_id, "status": "completed", "message": "Legacy endpoint"}

@app.get("/stats", tags=["Legacy"])
async def get_stats_legacy():
    """Get legacy parsing statistics."""
    return {
        "total_parsed": 0,
        "web_parsed": 0,
        "api_parsed": 0,
        "file_parsed": 0,
        "active_tasks": 0,
        "mode": "legacy_compatibility"
    }

# =============================================================================
# END LEGACY ENDPOINTS
# =============================================================================


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


# V1 Health endpoint for API compatibility
@app.get("/v1/health/", response_model=HealthResponse, tags=["V1 API"])
async def v1_health_check():
    """V1 API health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        platform_support=settings.SUPPORTED_PLATFORMS,
        details={
            "app_name": settings.APP_NAME,
            "api_version": "v1",
            "supported_platforms": [p.value for p in settings.SUPPORTED_PLATFORMS]
        }
    )

# V1 Tasks endpoints for API compatibility
@app.get("/v1/tasks/", tags=["V1 API"])
async def v1_list_tasks():
    """List all parsing tasks."""
    return {"tasks": [], "total": 0, "status": "coming_soon"}

@app.get("/v1/results/", tags=["V1 API"])
async def v1_list_results():
    """List parsing results."""
    return {"results": [], "total": 0, "status": "coming_soon"}

# Direct tasks endpoints (without v1 prefix) for frontend compatibility
@app.get("/tasks", tags=["Tasks API"])
async def list_tasks(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    """List all parsing tasks (frontend compatible endpoint)."""
    return {
        "tasks": [],
        "total": 0,
        "page": page,
        "limit": limit,
        "platforms": ["telegram", "instagram", "whatsapp"],
        "statuses": ["pending", "running", "completed", "failed", "paused"]
    }

@app.post("/tasks", tags=["Tasks API"])
async def create_task(task_data: dict):
    """Create new parsing task."""
    return {
        "task_id": f"task_{int(time.time())}",
        "status": "pending",
        "message": "Task created successfully",
        "platform": task_data.get("platform", "telegram"),
        "links": task_data.get("links", [])
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 