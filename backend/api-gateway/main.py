from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from typing import Dict
import httpx
import os
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
import time
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.decorator import limiter as slowapi_limiter
from redis import Redis
from middleware import CSRFMiddleware, RefreshTokenMiddleware
from itsdangerous import URLSafeTimedSerializer
import jwt
from datetime import datetime, timedelta
import logging
import json
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyHeader

load_dotenv()

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

app = FastAPI(
    title="Content Factory API Gateway",
    description="API Gateway for Content Factory SaaS Platform",
    version="1.0.0",
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None,
    openapi_url="/openapi.json"
)

# Redis client
redis_client = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0))
)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://92.113.146.148:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# CSRF middleware
app.add_middleware(
    CSRFMiddleware,
    secret_key=os.getenv("CSRF_SECRET_KEY", "your-secret-key")
)

# Refresh token middleware
app.add_middleware(
    RefreshTokenMiddleware,
    redis_client=redis_client,
    jwt_secret=os.getenv("JWT_SECRET_KEY", "your-jwt-secret")
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Service URLs (in production, these should be environment variables)
SERVICE_URLS = {
    "user": os.getenv("USER_SERVICE_URL", "http://92.113.146.148:8001"),
    "billing": os.getenv("BILLING_SERVICE_URL", "http://92.113.146.148:8002"),
    "admin": os.getenv("ADMIN_SERVICE_URL", "http://92.113.146.148:8003"),
    "scenario": os.getenv("SCENARIO_SERVICE_URL", "http://92.113.146.148:8004"),
    "content": os.getenv("CONTENT_SERVICE_URL", "http://92.113.146.148:8005"),
    "invite": os.getenv("INVITE_SERVICE_URL", "http://92.113.146.148:8006"),
    "parsing": os.getenv("PARSING_SERVICE_URL", "http://92.113.146.148:8007"),
    "integration": os.getenv("INTEGRATION_SERVICE_URL", "http://92.113.146.148:8008"),
}

# Настройка логирования (JSON в stdout)
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
        }
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)

logger = logging.getLogger("audit")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.setLevel(logging.INFO)
logger.addHandler(handler)

@app.middleware("http")
async def add_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

@app.get("/health")
async def health_check(request: Request) -> Dict[str, str]:
    """
    Health check endpoint for the API Gateway
    """
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    """
    return generate_latest()

@app.get("/services/health")
async def services_health_check(request: Request) -> Dict[str, Dict[str, str]]:
    """
    Health check for all microservices
    """
    health_status = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service, url in SERVICE_URLS.items():
            try:
                response = await client.get(f"{url}/health")
                health_status[service] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code
                }
            except httpx.ConnectError:
                health_status[service] = {
                    "status": "unhealthy",
                    "error": "Connection refused"
                }
            except httpx.TimeoutException:
                health_status[service] = {
                    "status": "unhealthy",
                    "error": "Connection timeout"
                }
            except Exception as e:
                health_status[service] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
    return health_status

@app.get("/csrf-token")
async def get_csrf_token():
    """
    Generate CSRF token for the frontend
    """
    serializer = URLSafeTimedSerializer(os.getenv("CSRF_SECRET_KEY", "your-secret-key"))
    token = serializer.dumps("csrf-token")
    return {"csrf_token": token}

@app.post("/auth/refresh")
@slowapi_limiter("5/minute")
async def refresh_token(request: Request):
    """
    Refresh JWT token using refresh token
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        logger.warning(json.dumps({"event": "refresh_token_missing", "ip": request.client.host}))
        raise HTTPException(status_code=401, detail="Refresh token missing")
        
    user_id = redis_client.get(f"refresh_token:{refresh_token}")
    if not user_id:
        logger.warning(json.dumps({"event": "invalid_refresh_token", "ip": request.client.host}))
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    # Generate new JWT token
    new_token = jwt.encode(
        {
            "sub": user_id,
            "exp": datetime.utcnow() + timedelta(minutes=15)
        },
        os.getenv("JWT_SECRET_KEY", "your-jwt-secret"),
        algorithm="HS256"
    )
    logger.info(json.dumps({"event": "refresh_token_success", "user_id": user_id.decode() if hasattr(user_id, 'decode') else str(user_id), "ip": request.client.host}))
    return {"access_token": new_token}

@app.post("/auth/login")
@slowapi_limiter("5/minute")
async def login(request: Request):
    """
    Проксирует login на user-service, логирует все попытки (успех/ошибка)
    """
    try:
        data = await request.json()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{SERVICE_URLS['user']}/auth/login", json=data)
        if resp.status_code == 200:
            logger.info(json.dumps({"event": "login_success", "email": data.get("email"), "ip": request.client.host}))
        else:
            logger.warning(json.dumps({"event": "login_failed", "email": data.get("email"), "ip": request.client.host, "status": resp.status_code, "error": resp.text}))
        return resp.json(), resp.status_code
    except Exception as e:
        logger.error(json.dumps({"event": "login_error", "ip": request.client.host, "error": str(e)}))
        raise HTTPException(status_code=500, detail="Internal error")

@app.post("/auth/logout")
async def logout(request: Request):
    """
    Проксирует logout на user-service, логирует все попытки
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{SERVICE_URLS['user']}/auth/logout", cookies=request.cookies)
        if resp.status_code == 200:
            logger.info(json.dumps({"event": "logout_success", "ip": request.client.host}))
        else:
            logger.warning(json.dumps({"event": "logout_failed", "ip": request.client.host, "status": resp.status_code, "error": resp.text}))
        return resp.json(), resp.status_code
    except Exception as e:
        logger.error(json.dumps({"event": "logout_error", "ip": request.client.host, "error": str(e)}))
        raise HTTPException(status_code=500, detail="Internal error")

@app.post("/auth/register")
@slowapi_limiter("5/minute")
async def register(request: Request):
    """
    Проксирует регистрацию на user-service, логирует все попытки
    """
    try:
        data = await request.json()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{SERVICE_URLS['user']}/auth/register", json=data)
        if resp.status_code == 200:
            logger.info(json.dumps({"event": "register_success", "email": data.get("email"), "ip": request.client.host}))
        else:
            logger.warning(json.dumps({"event": "register_failed", "email": data.get("email"), "ip": request.client.host, "status": resp.status_code, "error": resp.text}))
        return resp.json(), resp.status_code
    except Exception as e:
        logger.error(json.dumps({"event": "register_error", "ip": request.client.host, "error": str(e)}))
        raise HTTPException(status_code=500, detail="Internal error")

# Security schemes
jwt_scheme = APIKeyHeader(name="Authorization", auto_error=False)
csrf_scheme = APIKeyHeader(name="X-CSRF-Token", auto_error=False)

# Кастомизация OpenAPI схемы

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "JWT": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "JWT access token в формате 'Bearer <token>'"
        },
        "CSRF": {
            "type": "apiKey",
            "in": "header",
            "name": "X-CSRF-Token",
            "description": "CSRF-токен, получаемый с /csrf-token"
        }
    }
    # Применяем схемы по умолчанию для защищённых эндпоинтов
    for path, methods in openapi_schema["paths"].items():
        for method, details in methods.items():
            if path.startswith("/auth") or path.startswith("/user"):
                details.setdefault("security", []).append({"JWT": []})
                if method in ["post", "put", "delete"]:
                    details["security"].append({"CSRF": []})
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 