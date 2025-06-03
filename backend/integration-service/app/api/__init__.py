from fastapi import APIRouter
from .v1 import api_router as v1_router

api_router = APIRouter()

# Включаем версии API
api_router.include_router(v1_router, prefix="/v1") 