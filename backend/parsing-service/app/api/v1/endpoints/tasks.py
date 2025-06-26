"""Parse tasks API endpoints."""

from fastapi import APIRouter
from typing import List
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

# Импортируем created_tasks из main module для доступа к задачам
def get_created_tasks():
    """Получить список задач из main модуля."""
    import main
    return getattr(main, 'created_tasks', [])


@router.get("/")
async def list_tasks():
    """List all parsing tasks."""
    return {"tasks": [], "total": 0, "status": "coming_soon"}


@router.post("/")
async def create_task():
    """Create new parsing task."""
    return {"message": "Task creation endpoint - coming soon", "status": "not_implemented"}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """Get specific parsing task."""
    return {"task_id": task_id, "status": "coming_soon"}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete parsing task."""
    return {"task_id": task_id, "deleted": True, "status": "coming_soon"}


@router.get("/{task_id}/progress-stream")
async def stream_task_progress(task_id: str):
    """
    Server-Sent Events stream для real-time обновления прогресса задачи
    """
    async def event_generator():
        try:
            while True:
                # Получаем текущий прогресс задачи
                created_tasks = get_created_tasks()
                task = None
                for t in created_tasks:
                    if t["id"] == task_id:
                        task = t
                        break
                
                if not task:
                    yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                    break
                
                # Отправляем данные о прогрессе
                progress_data = {
                    "task_id": task_id,
                    "status": task["status"],
                    "progress": task["progress"],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                yield f"data: {json.dumps(progress_data)}\n\n"
                
                # Если задача завершена, останавливаем stream
                if task["status"] in ["completed", "failed", "cancelled"]:
                    break
                
                # Ждем 1 секунду перед следующим обновлением
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in progress stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    ) 