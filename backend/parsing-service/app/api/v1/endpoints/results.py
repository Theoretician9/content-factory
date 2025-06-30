"""Parse results API endpoints with user filtering."""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import json
import csv
import io

from app.database import get_db
from app.models.parse_result import ParseResult
from app.models.parse_task import ParseTask
from app.core.auth import get_user_id_from_request

router = APIRouter()

@router.get("/")
async def list_results(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """List parsing results with user filtering."""
    
    # Build base query with JOIN to ParseTask
    query = select(ParseResult).join(ParseTask, ParseResult.task_id == ParseTask.id)
    count_query = select(func.count(ParseResult.id)).select_from(
        ParseResult.__table__.join(ParseTask.__table__, ParseResult.task_id == ParseTask.id)
    )
    
    # Apply user filter
    if user_id is not None:
        query = query.where(ParseTask.user_id == user_id)
        count_query = count_query.where(ParseTask.user_id == user_id)
    
    # Apply platform filter
    if platform:
        query = query.where(ParseResult.platform == platform)
        count_query = count_query.where(ParseResult.platform == platform)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination and ordering
    query = query.order_by(ParseResult.created_at.desc()).offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    results = result.scalars().all()
    
    return {
        "items": [_format_result(r) for r in results],
        "total": total,
        "page": offset // limit + 1 if limit > 0 else 1,
        "page_size": limit,
        "has_more": offset + limit < total,
        "filters": {
            "user_id": user_id,
            "platform": platform
        }
    }

@router.get("/grouped")
async def list_results_grouped_by_task(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    db: AsyncSession = Depends(get_db)
):
    """List parsing results grouped by tasks for user."""
    
    # Query to get task summaries with result counts
    query = select(
        ParseTask.id,
        ParseTask.task_id,
        ParseTask.title,
        ParseTask.platform,
        ParseTask.status,
        ParseTask.created_at,
        ParseTask.config,
        func.count(ParseResult.id).label('total_results')
    ).outerjoin(
        ParseResult, ParseTask.id == ParseResult.task_id
    ).group_by(
        ParseTask.id, ParseTask.task_id, ParseTask.title, 
        ParseTask.platform, ParseTask.status, ParseTask.created_at, ParseTask.config
    )
    
    # Apply user filter
    if user_id is not None:
        query = query.where(ParseTask.user_id == user_id)
    
    # Order by creation date
    query = query.order_by(ParseTask.created_at.desc())
    
    result = await db.execute(query)
    tasks = result.all()
    
    formatted_tasks = []
    for task in tasks:
        # Extract target info from config
        config = task.config or {}
        targets = config.get('targets', [])
        target_url = targets[0] if targets else 'Unknown'
        
        formatted_tasks.append({
            "task_id": task.task_id,
            "platform": task.platform.value if hasattr(task.platform, 'value') else str(task.platform),
            "target_url": target_url,
            "title": task.title,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "total_results": task.total_results,
            "created_at": task.created_at.isoformat() if task.created_at else None
        })
    
    return {
        "tasks": formatted_tasks,
        "total_tasks": len(formatted_tasks)
    }

@router.get("/{task_id}")
async def get_result(
    task_id: str,
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    db: AsyncSession = Depends(get_db),
    format: Optional[str] = "json",
    platform_filter: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0
):
    """Get parsing results for specific task with user verification."""
    
    # Build query with user verification
    query = select(ParseResult).join(ParseTask, ParseResult.task_id == ParseTask.id)
    
    # Filter by task_id (string or int)
    try:
        task_id_int = int(task_id)
        query = query.where(ParseTask.id == task_id_int)
    except ValueError:
        query = query.where(ParseTask.task_id == task_id)
    
    # Apply user filter for security
    if user_id is not None:
        query = query.where(ParseTask.user_id == user_id)
    
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
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    format: str = "json",
    db: AsyncSession = Depends(get_db)
):
    """Export parsing result in specified format with user verification."""
    
    # Get all results for the task with user verification
    query = select(ParseResult).join(ParseTask, ParseResult.task_id == ParseTask.id)
    
    try:
        task_id_int = int(task_id)
        query = query.where(ParseTask.id == task_id_int)
    except ValueError:
        query = query.where(ParseTask.task_id == task_id)
    
    if user_id is not None:
        query = query.where(ParseTask.user_id == user_id)
        
    query = query.order_by(ParseResult.created_at.desc())
    
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
        "platform_id": result.author_id or result.content_id,
        "username": result.author_username,
        "display_name": result.author_name or result.content_text[:50] if result.content_text else "Unknown",
        "author_phone": result.author_phone,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "platform_specific_data": result.platform_data or {}
    }
