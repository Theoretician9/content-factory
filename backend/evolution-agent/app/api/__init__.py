from fastapi import APIRouter

from .v1.agents import router as agents_router


api_router = APIRouter()
api_router.include_router(agents_router, prefix="/v1/agents", tags=["evolution-agent"])

