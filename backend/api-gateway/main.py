from fastapi import FastAPI, HTTPException, Depends, Request, APIRouter
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
from slowapi.middleware import SlowAPIMiddleware
from redis import Redis
from middleware import CSRFMiddleware, RefreshTokenMiddleware
from itsdangerous import URLSafeTimedSerializer
import jwt
from datetime import datetime, timedelta
import logging
import json
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, EmailStr, constr
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from common.vault_client import VaultClient

load_dotenv()

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Получаем JWT секрет из Vault в самом начале  
vault_client = VaultClient()
try:
    # Для KV v2 правильный путь включает /data/
    JWT_SECRET_KEY = vault_client.get_secret("kv/data/jwt")['secret_key']
    print(f"✅ API Gateway: JWT секрет получен из Vault")
except Exception as e:
    # Fallback к environment variable
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-jwt-secret")
    print(f"⚠️ API Gateway: используется JWT секрет из ENV: {e}")

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
app.add_middleware(SlowAPIMiddleware)

# CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://content-factory.xyz,https://admin.content-factory.xyz,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# CSRF middleware
# app.add_middleware(
#     CSRFMiddleware,
#     secret_key=os.getenv("CSRF_SECRET_KEY", "your-secret-key")
# )

# Refresh token middleware  
app.add_middleware(
    RefreshTokenMiddleware,
    redis_client=redis_client,
    jwt_secret=JWT_SECRET_KEY
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
    "integration": os.getenv("INTEGRATION_SERVICE_URL", "http://integration-service:8000"),
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

api_router = APIRouter(prefix="/api")

@api_router.get("/health")
async def health_check(request: Request) -> Dict[str, str]:
    """
    Health check endpoint for the API Gateway
    """
    return {"status": "healthy", "service": "api-gateway"}

@api_router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    """
    return generate_latest()

@api_router.get("/services/health")
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

@api_router.get("/csrf-token")
async def get_csrf_token():
    """
    Generate CSRF token for the frontend
    """
    serializer = URLSafeTimedSerializer(os.getenv("CSRF_SECRET_KEY", "your-secret-key"))
    token = serializer.dumps("csrf-token")
    return {"csrf_token": token}

@api_router.post("/auth/refresh")
@limiter.limit("5/minute")
async def refresh_token(request: Request):
    """
    Refresh access token using refresh token
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
        JWT_SECRET_KEY,
        algorithm="HS256"
    )
    logger.info(json.dumps({"event": "refresh_token_success", "user_id": user_id.decode() if hasattr(user_id, 'decode') else str(user_id), "ip": request.client.host}))
    return {"access_token": new_token}

class LoginRequest(BaseModel):
    username: str = None
    email: EmailStr = None
    password: constr(min_length=8)

class RegisterRequest(BaseModel):
    email: EmailStr
    username: constr(min_length=3) = None
    password: constr(min_length=8)
    confirm_password: constr(min_length=8)
    agree: bool

@api_router.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    """
    Login user and return access token
    """
    try:
        data = body.dict()
        # Если username не передан, используем email как username
        if not data.get("username") and data.get("email"):
            data["username"] = data["email"]
        # Удаляем email, если он не нужен user-service
        data.pop("email", None)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{SERVICE_URLS['user']}/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        if resp.status_code == 200:
            logger.info(json.dumps({"event": "login_success", "email": data.get("username"), "ip": request.client.host}))
        else:
            logger.warning(json.dumps({"event": "login_failed", "email": data.get("username"), "ip": request.client.host, "status": resp.status_code, "error": resp.text}))
        # Возвращаем только объект токена, а не массив
        return resp.json()
    except Exception as e:
        logger.error(json.dumps({"event": "login_error", "ip": request.client.host, "error": str(e)}))
        raise HTTPException(status_code=500, detail="Internal error")

@api_router.post("/auth/logout")
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

@api_router.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest):
    """
    Register new user
    """
    try:
        data = body.dict()
        # Если username не передан, используем email как username
        if not data.get("username") and data.get("email"):
            data["username"] = data["email"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{SERVICE_URLS['user']}/users/", json=data)
        if resp.status_code == 200:
            logger.info(json.dumps({"event": "register_success", "email": data.get("email"), "ip": request.client.host}))
        else:
            logger.warning(json.dumps({"event": "register_failed", "email": data.get("email"), "ip": request.client.host, "status": resp.status_code, "error": resp.text}))
        return resp.json(), resp.status_code
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="User service unavailable")
    except Exception as e:
        logger.error(json.dumps({"event": "register_error", "ip": request.client.host, "error": str(e)}))
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/auth/me")
async def get_profile(request: Request):
    headers = {}
    if "authorization" in request.headers:
        headers["authorization"] = str(request.headers["authorization"])
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{SERVICE_URLS['user']}/users/me", headers=headers)
        return resp.json(), resp.status_code
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="User service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

# Глобальный обработчик ошибок валидации
from fastapi.exception_handlers import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError as FastAPIRequestValidationError

@app.exception_handler(FastAPIRequestValidationError)
async def validation_exception_handler(request: Request, exc: FastAPIRequestValidationError):
    logger.warning(json.dumps({"event": "validation_error", "ip": request.client.host, "errors": exc.errors()}))
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'; base-uri 'self';"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Integration Service proxy router
@app.api_route("/api/integrations/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_integration_service(request: Request, path: str):
    """
    Проксирование всех запросов к Integration Service
    """
    # Подготовка URL
    target_url = f"{SERVICE_URLS['integration']}/api/v1/{path}"
    
    # Копирование headers (включая Authorization)
    headers = {}
    for name, value in request.headers.items():
        if name.lower() not in ["host", "content-length"]:
            headers[name] = value
    
    # Логирование для отладки авторизации
    auth_header = headers.get("authorization", "MISSING")
    logger.info(json.dumps({
        "event": "proxy_to_integration_service", 
        "path": path, 
        "method": request.method,
        "auth_header": auth_header[:50] + "..." if len(auth_header) > 50 else auth_header,
        "target_url": target_url
    }))
    
    # Копирование query parameters
    query_params = str(request.url.query)
    if query_params:
        target_url += f"?{query_params}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Получение body для POST/PUT запросов
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # Выполнение запроса к Integration Service
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body
            )
            
            # Возврат ответа с оригинальными headers
            response_headers = dict(response.headers)
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response_headers.get("content-type")
            )
            
    except httpx.ConnectError:
        logger.error(json.dumps({"event": "integration_service_connection_error", "url": target_url}))
        raise HTTPException(status_code=502, detail="Integration service unavailable")
    except httpx.TimeoutException:
        logger.error(json.dumps({"event": "integration_service_timeout", "url": target_url}))
        raise HTTPException(status_code=504, detail="Integration service timeout")
    except Exception as e:
        logger.error(json.dumps({"event": "integration_service_error", "url": target_url, "error": str(e)}))
        raise HTTPException(status_code=500, detail="Internal server error")

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 