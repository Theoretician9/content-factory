"""Main API v1 router."""

from fastapi import APIRouter
from .endpoints import health, tasks, results

router = APIRouter(prefix="/v1")

# Include endpoint routers
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(tasks.router, prefix="/tasks", tags=["Parse Tasks"])
router.include_router(results.router, prefix="/results", tags=["Parse Results"])
# Note: search router is included directly in main.py for correct path routing
