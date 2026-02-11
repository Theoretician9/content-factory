import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.database import init_db, close_db


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом evolution-agent."""
    settings = get_settings()
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.VERSION}")

    # Инициализация БД
    try:
        await init_db()
        logger.info("✅ evolution-agent: database initialized successfully")
    except Exception as e:
        logger.error(f"❌ evolution-agent: failed to initialize database: {e}")
        # Для MVP не падаем, но логируем

    yield

    try:
        await close_db()
        logger.info("🛑 evolution-agent: database connections closed")
    except Exception as e:
        logger.error(f"❌ evolution-agent: error closing database connections: {e}")


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Evolution Agent — ИИ‑агент для ведения Telegram‑каналов",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # будет ужесточено при интеграции с фронтом
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Простейший корневой endpoint для проверки живости сервиса."""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "description": "Evolution Agent — MVP ИИ‑агента для Telegram‑канала",
    }


@app.get("/health")
async def health():
    """Health‑check для docker-compose и api-gateway."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик ошибок в JSON‑формате, дружелюбный к ELK."""
    logger.exception("Unhandled exception in evolution-agent", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An internal server error occurred in evolution-agent",
        },
    )
