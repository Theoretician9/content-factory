"""
API endpoints для работы с задачами парсинга
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
import logging
import httpx

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
        
        # 🔍 ДИАГНОСТИКА: логируем запрос к parsing-service
        logger.info(f"🔍 DIAGNOSTIC: Requesting parsing tasks for user_id={user_id}")
        
        # Получаем JWT токен для межсервисного взаимодействия
        token = await _get_jwt_token_for_parsing_service(user_id)
        
        parsing_service_url = "http://parsing-service:8000"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Запрашиваем grouped результаты от parsing-service
            response = await client.get(
                f"{parsing_service_url}/api/v1/results/grouped",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            # 🔍 ДИАГНОСТИКА: логируем ответ parsing-service
            logger.info(f"🔍 DIAGNOSTIC: Parsing-service response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                tasks = data.get('tasks', [])
                
                # 🔍 ДИАГНОСТИКА: логируем полученные данные
                logger.info(f"🔍 DIAGNOSTIC: Received {len(tasks)} tasks from parsing-service")
                for i, task in enumerate(tasks[:3]):  # Логируем первые 3 задачи
                    logger.info(f"🔍 DIAGNOSTIC: Task {i+1}: {task.get('task_id')} - {task.get('target_url')} ({task.get('total_results')} results)")
                
                # Преобразуем формат для совместимости с фронтендом
                formatted_tasks = []
                for task in tasks:
                    formatted_task = {
                        "id": task.get('task_id', 'unknown'),
                        "platform": task.get('platform', 'telegram'),
                        "status": task.get('status', 'completed'),
                        "result_count": task.get('total_results', 0),
                        "created_at": task.get('created_at', ''),
                        "link": task.get('target_url', 'Unknown'),
                        "task_type": "channel_members",
                        "title": f"Parse {task.get('target_url', 'Unknown')}"
                    }
                    formatted_tasks.append(formatted_task)
                
                logger.info(f"✅ Возвращаем {len(formatted_tasks)} задач парсинга для пользователя {user_id}")
                return formatted_tasks
            
            elif response.status_code == 401:
                logger.error(f"❌ Unauthorized access to parsing-service for user {user_id}")
                return []
            
            else:
                logger.error(f"❌ Error from parsing-service: {response.status_code}")
                return []
        
    except Exception as e:
        logger.error(f"❌ Error getting parsing tasks: {str(e)}")
        # 🔍 ДИАГНОСТИКА: детальная ошибка
        import traceback
        logger.error(f"❌ DIAGNOSTIC: Full error traceback: {traceback.format_exc()}")
        return []


@router.get("/parsing-tasks/{task_id}")
async def get_parsing_task_details(task_id: str, user_id: int = Depends(get_current_user_id)):
    """Получение детальной информации о задаче парсинга"""
    try:
        logger.info(f"🔍 DIAGNOSTIC: Getting details for task {task_id}, user {user_id}")
        
        # Получаем JWT токен
        token = await _get_jwt_token_for_parsing_service(user_id)
        
        parsing_service_url = "http://parsing-service:8000"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Запрашиваем конкретную задачу
            response = await client.get(
                f"{parsing_service_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                task_data = response.json()
                
                return {
                    "id": task_id,
                    "platform": task_data.get('platform', 'telegram'),
                    "status": task_data.get('status', 'completed'),
                    "result_count": task_data.get('result_count', 0),
                    "link": task_data.get('link', 'Unknown'),
                    "title": task_data.get('settings', {}).get('title', f"Parse {task_id}")
                }
            else:
                logger.error(f"❌ Error getting task details: {response.status_code}")
                raise HTTPException(status_code=404, detail="Task not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting task details: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _get_jwt_token_for_parsing_service(user_id: int) -> str:
    """Получение JWT токена для межсервисного взаимодействия с Parsing Service"""
    try:
        from app.core.vault import get_vault_client
        from datetime import datetime, timedelta
        
        vault_client = get_vault_client()
        secret_data = vault_client.get_secret("jwt")
        
        if not secret_data or 'secret_key' not in secret_data:
            raise Exception("JWT secret not found in Vault")
        
        # 🔍 ДИАГНОСТИКА: логируем создание токена
        logger.debug(f"🔍 DIAGNOSTIC: Creating JWT token for user_id={user_id}")
        
        # Создаем токен для invite-service с реальным user_id
        payload = {
            'service': 'invite-service',
            'user_id': user_id,  # ✅ Используем реальный user_id
            'exp': int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        
        import jwt
        token = jwt.encode(payload, secret_data['secret_key'], algorithm='HS256')
        
        logger.debug(f"🔍 DIAGNOSTIC: JWT token created successfully for user_id={user_id}")
        return token
        
    except Exception as e:
        logger.error(f"Error getting JWT token for parsing service: {e}")
        raise 