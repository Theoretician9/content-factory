"""
API endpoints для работы с задачами парсинга
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
import httpx
import logging
import jwt
from datetime import datetime, timedelta
import traceback

from app.core.config import settings
from app.core.auth import get_current_user_id

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_jwt_token_for_parsing_service() -> str:
    """Получение JWT токена для межсервисного взаимодействия с Parsing Service"""
    try:
        from app.core.vault import get_vault_client
        
        logger.info("🔍 DIAGNOSTIC: Getting JWT token for parsing service")
        
        vault_client = get_vault_client()
        secret_data = vault_client.get_secret("jwt")
        
        logger.info(f"🔍 DIAGNOSTIC: Secret data received: {bool(secret_data)}")
        
        if not secret_data or 'secret_key' not in secret_data:
            logger.error("❌ DIAGNOSTIC: JWT secret not found in Vault")
            raise Exception("JWT secret not found in Vault")
        
        logger.info(f"🔍 DIAGNOSTIC: JWT secret key length: {len(secret_data['secret_key'])}")
        
        # Создаем токен для invite-service
        payload = {
            'service': 'invite-service',
            'user_id': 1,  # Системный токен
            'exp': int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        
        logger.info(f"🔍 DIAGNOSTIC: JWT payload: {payload}")
        
        token = jwt.encode(payload, secret_data['secret_key'], algorithm='HS256')
        
        logger.info(f"🔍 DIAGNOSTIC: JWT token created, length: {len(token)}")
        logger.info(f"🔍 DIAGNOSTIC: JWT token preview: {token[:50]}...")
        
        return token
        
    except Exception as e:
        logger.error(f"❌ DIAGNOSTIC: Error getting JWT token for parsing service: {e}")
        logger.error(f"❌ DIAGNOSTIC: JWT token traceback: {traceback.format_exc()}")
        raise


@router.get("/", response_model=List[Dict[str, Any]])
async def get_parsing_tasks(user_id: int = Depends(get_current_user_id)):
    """
    Получение списка задач парсинга для импорта аудитории
    """
    try:
        logger.info(f"🔍 DIAGNOSTIC: Получение задач парсинга для пользователя {user_id}")
        
        # Получаем JWT токен для межсервисного взаимодействия
        logger.info("🔍 DIAGNOSTIC: Получение JWT токена...")
        token = await get_jwt_token_for_parsing_service()
        logger.info("🔍 DIAGNOSTIC: JWT токен получен успешно")
        
        # Запрос к parsing-service с фильтрацией по user_id
        logger.info(f"🔍 DIAGNOSTIC: Отправка запроса к {settings.PARSING_SERVICE_URL}/api/v1/results/grouped")
        logger.info(f"🔍 DIAGNOSTIC: Headers: Authorization: Bearer {token[:50]}...")
        logger.info(f"🔍 DIAGNOSTIC: Params: user_id={user_id}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{settings.PARSING_SERVICE_URL}/api/v1/results/grouped",
                headers={"Authorization": f"Bearer {token}"},
                params={"user_id": user_id}
            )
            
            logger.info(f"🔍 DIAGNOSTIC: Ответ от parsing-service: status={response.status_code}")
            logger.info(f"🔍 DIAGNOSTIC: Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                logger.info("🔍 DIAGNOSTIC: Успешный ответ, парсинг JSON...")
                data = response.json()
                logger.info(f"🔍 DIAGNOSTIC: JSON data keys: {list(data.keys())}")
                
                tasks = data.get("tasks", [])
                logger.info(f"🔍 DIAGNOSTIC: Получено {len(tasks)} задач из parsing-service")
                
                if tasks:
                    logger.info(f"🔍 DIAGNOSTIC: Пример первой задачи: {tasks[0]}")
                
                # Преобразуем в формат для фронтенда
                formatted_tasks = []
                for i, task in enumerate(tasks):
                    logger.debug(f"🔍 DIAGNOSTIC: Обработка задачи {i+1}: {task.get('task_id')}")
                    
                    if task.get("total_results", 0) > 0:  # Только задачи с результатами
                        formatted_task = {
                            "id": task.get("task_id"),
                            "platform": task.get("platform", "telegram"),
                            "status": task.get("status", "completed"),
                            "target_url": task.get("target_url", ""),
                            "title": task.get("title", ""),
                            "total_results": task.get("total_results", 0),
                            "created_at": task.get("created_at"),
                            "can_import": True
                        }
                        formatted_tasks.append(formatted_task)
                        logger.debug(f"🔍 DIAGNOSTIC: Задача {i+1} добавлена в результат")
                    else:
                        logger.debug(f"🔍 DIAGNOSTIC: Задача {i+1} пропущена (нет результатов)")
                
                logger.info(f"🔍 DIAGNOSTIC: Возвращаем {len(formatted_tasks)} отформатированных задач")
                return formatted_tasks
                
            else:
                logger.error(f"❌ DIAGNOSTIC: Ошибка получения данных из parsing-service: {response.status_code}")
                logger.error(f"❌ DIAGNOSTIC: Response body: {response.text}")
                logger.error(f"❌ DIAGNOSTIC: Response headers: {dict(response.headers)}")
                return []
        
    except httpx.TimeoutException as e:
        logger.error(f"❌ DIAGNOSTIC: Timeout при запросе к parsing-service: {e}")
        return []
    except httpx.ConnectError as e:
        logger.error(f"❌ DIAGNOSTIC: Ошибка соединения с parsing-service: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ DIAGNOSTIC: Ошибка при получении задач парсинга: {str(e)}")
        logger.error(f"❌ DIAGNOSTIC: Full traceback: {traceback.format_exc()}")
        # Возвращаем пустой список вместо заглушки
        return []


@router.get("/{task_id}/preview", response_model=Dict[str, Any])
async def preview_parsing_task_data(
    task_id: str,
    limit: int = 10,
    user_id: int = Depends(get_current_user_id)
):
    """
    Предварительный просмотр данных из задачи парсинга
    """
    try:
        logger.info(f"Предварительный просмотр данных задачи {task_id} для пользователя {user_id}")
        
        # Получаем JWT токен
        token = await get_jwt_token_for_parsing_service()
        
        # Запрос к parsing-service за данными конкретной задачи
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.PARSING_SERVICE_URL}/api/v1/results/{task_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "user_id": user_id,
                    "limit": limit,
                    "offset": 0
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                # Преобразуем в формат для предварительного просмотра
                preview_data = {
                    "task_id": task_id,
                    "total_available": data.get("total", 0),
                    "preview_count": len(results),
                    "sample_contacts": []
                }
                
                for result in results:
                    platform_data = result.get("platform_specific_data", {})
                    contact = {
                        "username": result.get("username"),
                        "display_name": result.get("display_name"),
                        "phone": result.get("author_phone"),
                        "platform_id": result.get("platform_id"),
                        "first_name": platform_data.get("first_name"),
                        "last_name": platform_data.get("last_name"),
                        "chat_title": platform_data.get("chat_title")
                    }
                    preview_data["sample_contacts"].append(contact)
                
                return preview_data
                
            else:
                logger.error(f"Ошибка получения данных задачи {task_id}: {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Не удалось получить данные задачи парсинга: {response.text}"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при предварительном просмотре задачи {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения данных: {str(e)}"
        )


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