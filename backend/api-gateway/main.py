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

load_dotenv()

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Content Factory API Gateway",
    description="API Gateway for Content Factory SaaS Platform",
    version="1.0.0"
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
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
    "user": os.getenv("USER_SERVICE_URL", "http://user-service:8000"),
    "billing": os.getenv("BILLING_SERVICE_URL", "http://billing-service:8000"),
    "admin": os.getenv("ADMIN_SERVICE_URL", "http://admin-service:8000"),
    "scenario": os.getenv("SCENARIO_SERVICE_URL", "http://scenario-service:8000"),
    "content": os.getenv("CONTENT_SERVICE_URL", "http://content-service:8000"),
    "invite": os.getenv("INVITE_SERVICE_URL", "http://invite-service:8000"),
    "parsing": os.getenv("PARSING_SERVICE_URL", "http://parsing-service:8000"),
    "integration": os.getenv("INTEGRATION_SERVICE_URL", "http://integration-service:8000"),
}

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
@limiter.limit("5/minute")
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
@limiter.limit("10/minute")
async def services_health_check() -> Dict[str, Dict[str, str]]:
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 