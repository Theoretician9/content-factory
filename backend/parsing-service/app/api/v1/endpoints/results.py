"""Parse results API endpoints with user filtering."""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import json
import csv
import io
import logging
import traceback

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
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List parsing results grouped by tasks for user."""
    
    logger = logging.getLogger(__name__)
    logger.info("🔍 DIAGNOSTIC: Starting /grouped endpoint")
    
    # ✅ JWT АВТОРИЗАЦИЯ: Получаем user_id из JWT токена  
    try:
        logger.info("🔍 DIAGNOSTIC: Starting JWT authentication")
        user_id = await get_user_id_from_request(request)
        logger.info(f"🔐 JWT Authorization successful for grouped endpoint: user_id={user_id}")
    except Exception as auth_error:
        logger.error(f"❌ JWT Authorization failed for grouped endpoint: {auth_error}")
        logger.error(f"❌ DIAGNOSTIC: Full auth traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=401, detail=f"Authorization failed: {str(auth_error)}")
    
    try:
        logger.info(f"🔍 DIAGNOSTIC: Building SQL query for user_id={user_id}")
        
        # Query to get task summaries with result counts (без config в GROUP BY)
        query = select(
            ParseTask.id,
            ParseTask.task_id,
            ParseTask.title,
            ParseTask.platform,
            ParseTask.status,
            ParseTask.created_at,
            func.count(ParseResult.id).label('total_results')
        ).outerjoin(
            ParseResult, ParseTask.id == ParseResult.task_id
        ).group_by(
            ParseTask.id, ParseTask.task_id, ParseTask.title, 
            ParseTask.platform, ParseTask.status, ParseTask.created_at
        )
        
        logger.info("🔍 DIAGNOSTIC: Query built successfully")
        
        # Apply user filter from JWT token
        query = query.where(ParseTask.user_id == user_id)
        logger.info(f"🔍 DIAGNOSTIC: User filter applied for user_id={user_id}")
        
        # Order by creation date
        query = query.order_by(ParseTask.created_at.desc())
        logger.info("🔍 DIAGNOSTIC: Query ordering applied")
        
        logger.info("🔍 DIAGNOSTIC: Executing database query...")
        result = await db.execute(query)
        logger.info("🔍 DIAGNOSTIC: Database query executed successfully")
        
        tasks = result.all()
        logger.info(f"🔍 DIAGNOSTIC: Found {len(tasks)} tasks in database")
        
        # Получаем config для каждой задачи отдельно
        formatted_tasks = []
        for i, task in enumerate(tasks):
            try:
                logger.debug(f"🔍 DIAGNOSTIC: Processing task {i+1}/{len(tasks)}: {task.task_id}")
                
                # Получаем config отдельным запросом
                config_query = select(ParseTask.config).where(ParseTask.id == task.id)
                config_result = await db.execute(config_query)
                config = config_result.scalar() or {}
                
                # Extract target info from config
                targets = config.get('targets', [])
                target_url = targets[0] if targets else 'Unknown'
                
                formatted_task = {
                    "task_id": task.task_id,
                    "platform": task.platform.value if hasattr(task.platform, 'value') else str(task.platform),
                    "target_url": target_url,
                    "title": task.title,
                    "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                    "total_results": task.total_results,
                    "created_at": task.created_at.isoformat() if task.created_at else None
                }
                
                formatted_tasks.append(formatted_task)
                logger.debug(f"🔍 DIAGNOSTIC: Task {i+1} formatted successfully")
                
            except Exception as task_error:
                logger.error(f"❌ DIAGNOSTIC: Error processing task {i+1}: {task_error}")
                logger.error(f"❌ DIAGNOSTIC: Task data: {task}")
                logger.error(f"❌ DIAGNOSTIC: Task processing traceback: {traceback.format_exc()}")
        
        response_data = {
            "tasks": formatted_tasks,
            "total_tasks": len(formatted_tasks),
            "user_id": user_id  # Для отладки
        }
        
        logger.info(f"🔍 DIAGNOSTIC: Returning {len(formatted_tasks)} formatted tasks")
        return response_data
        
    except Exception as e:
        logger.error(f"❌ DIAGNOSTIC: Critical error in /grouped endpoint: {e}")
        logger.error(f"❌ DIAGNOSTIC: Full traceback: {traceback.format_exc()}")
        logger.error(f"❌ DIAGNOSTIC: Request headers: {dict(request.headers)}")
        logger.error(f"❌ DIAGNOSTIC: User ID: {user_id if 'user_id' in locals() else 'NOT_SET'}")
        
        # Возвращаем детальную ошибку для диагностики
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "internal_server_error",
                "message": f"Database query failed: {str(e)}",
                "details": str(e),
                "user_id": user_id if 'user_id' in locals() else None
            }
        )

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
