from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from typing import Dict
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Content Factory API Gateway",
    description="API Gateway for Content Factory SaaS Platform",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Service URLs (in production, these should be environment variables)
SERVICE_URLS = {
    "user": "http://user-service:8000",
    "billing": "http://billing-service:8000",
    "admin": "http://admin-service:8000",
    "scenario": "http://scenario-service:8000",
    "content": "http://content-service:8000",
    "invite": "http://invite-service:8000",
    "parsing": "http://parsing-service:8000",
    "integration": "http://integration-service:8000",
}

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint for the API Gateway
    """
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/services/health")
async def services_health_check() -> Dict[str, Dict[str, str]]:
    """
    Health check for all microservices
    """
    health_status = {}
    async with httpx.AsyncClient() as client:
        for service, url in SERVICE_URLS.items():
            try:
                response = await client.get(f"{url}/health")
                health_status[service] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code
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