"""
API endpoints для работы с задачами парсинга
"""

from fastapi import APIRouter, Depends
from typing import List, Dict, Any
import logging

from app.core.auth import get_current_user_id

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/parsing-tasks", response_model=List[Dict[str, Any]])
async def get_parsing_tasks(user_id: int = Depends(get_current_user_id)):
    """
    Получение списка задач парсинга для импорта аудитории
    """
    try:
        logger.info(f"Получение задач парсинга для пользователя {user_id}")
        # TODO: Реализовать интеграцию с parsing-service
        return [
            {
                "id": "parse_001",
                "platform": "telegram",
                "status": "completed",
                "result_count": 1250,
                "created_at": "2024-12-28T10:30:00Z",
                "link": "https://t.me/python_chat",
                "task_type": "channel_members",
                "title": "Python Developers Chat"
            },
            {
                "id": "parse_002", 
                "platform": "telegram",
                "status": "completed",
                "result_count": 890,
                "created_at": "2024-12-27T15:45:00Z",
                "link": "https://t.me/it_jobs", 
                "task_type": "channel_members",
                "title": "IT Jobs Channel"
            }
        ]
        
    except Exception as e:
        logger.error(f"Error getting parsing tasks: {str(e)}")
        return []


@router.get("/parsing-tasks/{task_id}")
async def get_parsing_task_details(task_id: str, user_id: int = Depends(get_current_user_id)):
    """Получение детальной информации о задаче парсинга"""
    return {
        "id": task_id,
        "platform": "telegram",
        "status": "completed",
        "result_count": 1250,
        "link": "https://t.me/python_chat",
        "title": "Python Developers Chat"
    } 