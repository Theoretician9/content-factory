"""
API endpoints для работы с задачами парсинга
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
import httpx
import logging
import jwt

from app.core.config import settings
from app.core.auth import get_current_user_id

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_jwt_token_for_parsing_service() -> str:
    """Получение JWT токена для межсервисного взаимодействия с Parsing Service"""
    try:
        from app.core.vault import get_vault_client
        
        vault_client = get_vault_client()
        secret_data = vault_client.get_secret("jwt")
        
        if not secret_data or 'secret_key' not in secret_data:
            raise Exception("JWT secret not found in Vault")
        
        # Создаем токен для invite-service
        payload = {
            'service': 'invite-service',
            'user_id': 1,  # Системный токен
            'exp': jwt.utils.get_int_from_datetime(
                jwt.datetime.datetime.utcnow() + jwt.datetime.timedelta(hours=1)
            )
        }
        
        token = jwt.encode(payload, secret_data['secret_key'], algorithm='HS256')
        return token
        
    except Exception as e:
        logger.error(f"Error getting JWT token for parsing service: {e}")
        raise


@router.get("/", response_model=List[Dict[str, Any]])
async def get_parsing_tasks(user_id: int = Depends(get_current_user_id)):
    """
    Получение списка задач парсинга для импорта аудитории из Parsing Service
    """
    try:
        logger.info(f"Получение задач парсинга для пользователя {user_id}")
        
        # Получаем JWT токен для авторизации в parsing-service
        try:
            token = await get_jwt_token_for_parsing_service()
        except Exception as e:
            logger.warning(f"Failed to get JWT token: {e}. Using fallback data.")
            # Возвращаем заглушку если не удается получить токен
            return await _get_fallback_parsing_tasks(user_id)
        
        # URL parsing-service
        parsing_service_url = "http://parsing-service:8000"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Получаем список задач парсинга через прямой API
                response = await client.get(
                    f"{parsing_service_url}/tasks",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    tasks_data = response.json()
                    
                    # Фильтруем задачи по пользователю и статусу "completed"
                    user_tasks = []
                    for task in tasks_data.get('tasks', []):
                        if (task.get('user_id') == user_id and 
                            task.get('status') == 'completed'):
                            
                            # Конвертируем в формат для invite-service
                            converted_task = {
                                "id": task.get('task_id', task.get('id')),
                                "platform": task.get('platform', 'telegram'),
                                "status": task.get('status'),
                                "result_count": task.get('result_count', 0),
                                "created_at": task.get('created_at'),
                                "completed_at": task.get('completed_at'),
                                "link": task.get('target_link', task.get('link')),
                                "task_type": task.get('task_type', 'channel_members'),
                                "title": task.get('title', task.get('channel_name', 'Unknown')),
                                "description": task.get('description', f"Результаты парсинга {task.get('platform', 'telegram')}")
                            }
                            user_tasks.append(converted_task)
                    
                    logger.info(f"Получено {len(user_tasks)} задач парсинга для пользователя {user_id}")
                    return user_tasks
                
                else:
                    logger.warning(f"Parsing service returned {response.status_code}: {response.text}")
                    return await _get_fallback_parsing_tasks(user_id)
                    
            except httpx.TimeoutException:
                logger.warning("Timeout connecting to parsing-service")
                return await _get_fallback_parsing_tasks(user_id)
            except httpx.ConnectError:
                logger.warning("Cannot connect to parsing-service")
                return await _get_fallback_parsing_tasks(user_id)
        
    except Exception as e:
        logger.error(f"Error getting parsing tasks: {str(e)}")
        return await _get_fallback_parsing_tasks(user_id)


async def _get_fallback_parsing_tasks(user_id: int) -> List[Dict[str, Any]]:
    """Fallback данные если parsing-service недоступен"""
    logger.info(f"Возвращаем fallback данные для пользователя {user_id}")
    return [
        {
            "id": "fallback_001",
            "platform": "telegram",
            "status": "completed",
            "result_count": 156,
            "created_at": "2025-01-30T10:30:00Z",
            "completed_at": "2025-01-30T10:45:00Z",
            "link": "https://t.me/rflive", 
            "task_type": "channel_members",
            "title": "RFLive Test Channel",
            "description": "Тестовые результаты парсинга (fallback)"
        }
    ]


@router.get("/{task_id}")
async def get_parsing_task_details(task_id: str, user_id: int = Depends(get_current_user_id)):
    """Получение детальной информации о задаче парсинга"""
    try:
        logger.info(f"Получение деталей задачи парсинга {task_id} для пользователя {user_id}")
        
        # Получаем JWT токен для авторизации
        try:
            token = await get_jwt_token_for_parsing_service()
        except Exception as e:
            logger.warning(f"Failed to get JWT token: {e}. Using fallback data.")
            return await _get_fallback_task_details(task_id, user_id)
        
        parsing_service_url = "http://parsing-service:8000"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Получаем детали задачи
                response = await client.get(
                    f"{parsing_service_url}/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    task_data = response.json()
                    
                    # Проверяем принадлежность пользователю
                    if task_data.get('user_id') != user_id:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Task not found"
                        )
                    
                    # Получаем preview результатов
                    results_preview = []
                    try:
                        results_response = await client.get(
                            f"{parsing_service_url}/results/{task_id}?limit=5",
                            headers={"Authorization": f"Bearer {token}"}
                        )
                        if results_response.status_code == 200:
                            results_data = results_response.json()
                            for result in results_data.get('results', [])[:5]:
                                results_preview.append({
                                    "username": result.get('username', ''),
                                    "first_name": result.get('display_name', '').split()[0] if result.get('display_name') else '',
                                    "last_name": ' '.join(result.get('display_name', '').split()[1:]) if result.get('display_name') else '',
                                    "phone": result.get('author_phone', '')
                                })
                    except Exception as e:
                        logger.warning(f"Could not get results preview: {e}")
                    
                    return {
                        "id": task_data.get('task_id', task_id),
                        "platform": task_data.get('platform', 'telegram'),
                        "status": task_data.get('status'),
                        "result_count": task_data.get('result_count', 0),
                        "created_at": task_data.get('created_at'),
                        "completed_at": task_data.get('completed_at'),
                        "link": task_data.get('target_link', task_data.get('link')),
                        "task_type": task_data.get('task_type', 'channel_members'),
                        "title": task_data.get('title', task_data.get('channel_name')),
                        "description": task_data.get('description'),
                        "results_preview": results_preview,
                        "statistics": {
                            "total_found": task_data.get('result_count', 0),
                            "with_username": len([r for r in results_preview if r.get('username')]),
                            "with_phone": len([r for r in results_preview if r.get('phone')]),
                            "active_users": task_data.get('result_count', 0),
                            "bots": 0
                        }
                    }
                
                elif response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Task not found")
                else:
                    logger.warning(f"Parsing service returned {response.status_code}")
                    return await _get_fallback_task_details(task_id, user_id)
                    
            except httpx.TimeoutException:
                logger.warning("Timeout connecting to parsing-service")
                return await _get_fallback_task_details(task_id, user_id)
            except httpx.ConnectError:
                logger.warning("Cannot connect to parsing-service")
                return await _get_fallback_task_details(task_id, user_id)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task details: {str(e)}")
        return await _get_fallback_task_details(task_id, user_id)


async def _get_fallback_task_details(task_id: str, user_id: int) -> Dict[str, Any]:
    """Fallback детали задачи"""
    return {
        "id": task_id,
        "platform": "telegram", 
        "status": "completed",
        "result_count": 156,
        "created_at": "2025-01-30T10:30:00Z",
        "completed_at": "2025-01-30T10:45:00Z",
        "link": "https://t.me/rflive",
        "task_type": "channel_members",
        "title": "RFLive Test Channel (fallback)",
        "description": "Fallback данные задачи парсинга",
        "results_preview": [
            {
                "username": "@test_user1",
                "first_name": "Test",
                "last_name": "User1", 
                "phone": "+1234567890"
            }
        ],
        "statistics": {
            "total_found": 156,
            "with_username": 120,
            "with_phone": 85,
            "active_users": 140,
            "bots": 5
        }
    }


@router.get("/{task_id}/download")
async def download_parsing_results(task_id: str, user_id: int = Depends(get_current_user_id)):
    """Скачать результаты парсинга в формате JSON"""
    logger.info(f"Скачивание результатов парсинга {task_id} для пользователя {user_id}")
    
    # Проверяем доступ к задаче через детали
    task_details = await get_parsing_task_details(task_id, user_id)
    
    return {
        "task_id": task_id,
        "download_url": f"/api/v1/parsing-tasks/{task_id}/data",
        "format": "json",
        "size": f"{task_details.get('result_count', 0) * 0.1:.0f}KB",
        "expires_at": "2025-01-31T10:30:00Z"
    } 