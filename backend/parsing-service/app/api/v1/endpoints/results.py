"""Parse results API endpoints."""

from fastapi import APIRouter
from typing import List

router = APIRouter()


@router.get("/")
async def list_results():
    """List parsing results."""
    return {"results": [], "total": 0, "status": "coming_soon"}


@router.get("/{result_id}")
async def get_result(result_id: str):
    """Get specific parsing result."""
    return {"result_id": result_id, "status": "coming_soon"}


@router.get("/{result_id}/export")
async def export_result(result_id: str, format: str = "json"):
    """Export parsing result in specified format."""
    return {"result_id": result_id, "format": format, "status": "coming_soon"}
