"""
Invite Service - Микросервис для массовых рассылок и приглашений в мессенджеры
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import create_tables
from app.api.v1.router import api_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("🚀 Starting Invite Service...")
    await create_tables()
    logger.info("✅ Invite Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Invite Service...")


# Создание FastAPI приложения
app = FastAPI(
    title="Invite Service API",
    description="Микросервис для массовых рассылок и приглашений в мессенджеры",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Обработчик HTTP исключений"""
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации"""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "status_code": 422}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик общих исключений"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "status_code": 500}
    )


# Подключение роутеров
app.include_router(api_router, prefix="/api/v1")


# Health check
@app.get("/health")
async def health_check():
    """Базовый health check"""
    return {"status": "healthy", "service": "invite-service"}

@app.delete("/admin/clear-all-tasks")
async def clear_all_tasks():
    """Clear all invite tasks (database) and release accounts."""
    try:
        from app.clients.account_manager_client import AccountManagerClient
        from app.core.database import get_db_session
        from app.models import InviteTask, InviteTarget, InviteExecutionLog
        from sqlalchemy import select, delete
        
        account_manager = AccountManagerClient()
        
        # Clear database tasks
        with get_db_session() as db:
            # Get count before deletion
            tasks_count = db.query(InviteTask).count()
            targets_count = db.query(InviteTarget).count()
            logs_count = db.query(InviteExecutionLog).count()
            
            # Delete all related data
            if logs_count > 0:
                db.query(InviteExecutionLog).delete()
                logger.info(f"🗑️ Cleared {logs_count} execution logs")
            
            if targets_count > 0:
                db.query(InviteTarget).delete()
                logger.info(f"🗑️ Cleared {targets_count} invite targets")
            
            if tasks_count > 0:
                db.query(InviteTask).delete()
                logger.info(f"🗑️ Cleared {tasks_count} invite tasks")
            
            db.commit()
        
        # Release all locked accounts
        try:
            release_result = await account_manager.release_all_accounts()
            logger.info(f"🔓 Released accounts: {release_result}")
        except Exception as release_error:
            logger.warning(f"⚠️ Failed to release accounts: {release_error}")
            release_result = {"error": str(release_error)}
        
        return {
            "success": True,
            "message": "All invite tasks cleared and accounts released",
            "details": {
                "tasks_cleared": tasks_count,
                "targets_cleared": targets_count,
                "logs_cleared": logs_count,
                "account_release_result": release_result
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error clearing all tasks: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to clear all tasks"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 