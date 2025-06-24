"""Parse results API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import json
import csv
import io

from app.database import get_db
from app.models.parse_result import ParseResult

router = APIRouter()

@router.get("/")
async def list_results(db: AsyncSession = Depends(get_db)):
    """List all parsing results."""
    result = await db.execute(
        select(func.count(ParseResult.id)).select_from(ParseResult)
    )
    total = result.scalar() or 0
    
    # Get sample results
    result = await db.execute(
        select(ParseResult).limit(100).order_by(ParseResult.created_at.desc())
    )
    results = result.scalars().all()
    
    return {
        "results": [_format_result(r) for r in results],
        "total": total,
        "status": "active"
    }

@router.get("/{task_id}")
async def get_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    format: Optional[str] = "json",
    platform_filter: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0
):
    """Get parsing results for specific task."""
    
    # Build query
    query = select(ParseResult).where(ParseResult.task_id == task_id)
    
    # Apply platform filter
    if platform_filter:
        query = query.where(ParseResult.platform == platform_filter)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination and ordering
    query = query.order_by(ParseResult.created_at.desc()).offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    results = result.scalars().all()
    
    # If no results found, return empty but don't generate mock data
    if not results:
        return {
            "task_id": task_id,
            "results": [],
            "total": 0,
            "format": format,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "has_more": False
            },
            "message": "No parsing results found for this task. The task may still be running or no data was collected."
        }
    
    return {
        "task_id": task_id,
        "results": [_format_result(r) for r in results],
        "total": total,
        "format": format,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total
        }
    }

@router.get("/{task_id}/export")
async def export_result(
    task_id: str, 
    format: str = "json",
    db: AsyncSession = Depends(get_db)
):
    """Export parsing result in specified format."""
    
    # Get all results for the task
    query = select(ParseResult).where(ParseResult.task_id == task_id).order_by(ParseResult.created_at.desc())
    result = await db.execute(query)
    results = result.scalars().all()
    
    if not results:
        raise HTTPException(status_code=404, detail="No results found for this task")
    
    # Format results for export
    formatted_results = [_format_result(r) for r in results]
    
    # Export in JSON
    if format.lower() == "json":
        json_content = json.dumps(formatted_results, ensure_ascii=False, indent=2)
        return StreamingResponse(
            io.BytesIO(json_content.encode('utf-8')),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=parsing_results_{task_id}.json"}
        )
    
    # Export in CSV
    elif format.lower() == "csv":
        output = io.StringIO()
        if formatted_results:
            # Flatten the data for CSV
            flattened_results = []
            for result in formatted_results:
                flat_result = {
                    "id": result["id"],
                    "task_id": result["task_id"],
                    "platform": result["platform"],
                    "platform_id": result["platform_id"],
                    "username": result.get("username", ""),
                    "display_name": result.get("display_name", ""),
                    "author_phone": result.get("author_phone", ""),
                    "created_at": result["created_at"],
                }
                
                # Add platform-specific data as separate columns
                if result.get("platform_specific_data"):
                    for k, v in result["platform_specific_data"].items():
                        flat_result[f"specific_{k}"] = str(v) if v is not None else ""
                
                flattened_results.append(flat_result)
            
            if flattened_results:
                writer = csv.DictWriter(output, fieldnames=flattened_results[0].keys())
                writer.writeheader()
                writer.writerows(flattened_results)
        
        csv_content = output.getvalue()
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=parsing_results_{task_id}.csv"}
        )
    
    # Export in NDJSON (newline-delimited JSON)
    elif format.lower() == "ndjson":
        ndjson_lines = [json.dumps(result, ensure_ascii=False) for result in formatted_results]
        ndjson_content = "\n".join(ndjson_lines)
        return StreamingResponse(
            io.BytesIO(ndjson_content.encode('utf-8')),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f"attachment; filename=parsing_results_{task_id}.ndjson"}
        )
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use 'json', 'csv', or 'ndjson'")

def _format_result(result: ParseResult) -> dict:
    """Format ParseResult model for API response."""
    return {
        "id": str(result.id),
        "task_id": str(result.task_id),
        "platform": result.platform.value if hasattr(result.platform, 'value') else str(result.platform),
        "platform_id": result.author_id or result.content_id,  # Use author_id for user results
        "username": result.author_username,
        "display_name": result.author_name or result.content_text[:50] if result.content_text else "Unknown",
        "author_phone": result.author_phone,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "platform_specific_data": result.platform_data or {}
    }
