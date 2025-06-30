"""
Диагностические утилиты для отладки проблем Invite Service
"""

import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
import httpx
import jwt
from datetime import datetime, timedelta

from app.core.database import get_db_session
from app.models import InviteTask, InviteTarget, TaskStatus, TargetStatus
from app.core.auth import get_current_user_id

logger = logging.getLogger(__name__)


class InviteServiceDiagnostics:
    """Класс для диагностики проблем Invite Service"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def diagnose_task_execution_issue(self, task_id: int, user_id: int) -> Dict[str, Any]:
        """Диагностика проблем с запуском задач"""
        
        with get_db_session() as db:
            # Получение задачи
            task = db.query(InviteTask).filter(
                InviteTask.id == task_id,
                InviteTask.user_id == user_id
            ).first()
            
            if not task:
                return {
                    "issue": "task_not_found",
                    "details": f"Задача {task_id} не найдена для пользователя {user_id}"
                }
            
            # Проверка статуса
            if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
                return {
                    "issue": "invalid_status",
                    "details": f"Задача имеет статус {task.status}, должен быть PENDING или PAUSED",
                    "current_status": task.status.value
                }
            
            # Проверка целевой аудитории
            target_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count()
            
            if target_count == 0:
                return {
                    "issue": "no_targets",
                    "details": "В задаче нет целевой аудитории",
                    "target_count": 0,
                    "task_target_count_field": task.target_count,
                    "recommendation": "Загрузите аудиторию через файл или импорт из результатов парсинга"
                }
            
            # Проверка расхождения счетчиков
            if task.target_count != target_count:
                return {
                    "issue": "count_mismatch",
                    "details": f"Несоответствие счетчиков: task.target_count={task.target_count}, реальное количество={target_count}",
                    "real_count": target_count,
                    "task_count": task.target_count,
                    "recommendation": "Обновите счетчик в задаче"
                }
            
            # Проверка статусов целей
            target_stats = db.query(
                InviteTarget.status,
                func.count(InviteTarget.id).label('count')
            ).filter(
                InviteTarget.task_id == task_id
            ).group_by(InviteTarget.status).all()
            
            status_counts = {stat.status.value: stat.count for stat in target_stats}
            pending_count = status_counts.get('pending', 0)
            
            if pending_count == 0:
                return {
                    "issue": "no_pending_targets",
                    "details": "Нет целей в статусе PENDING для обработки",
                    "status_breakdown": status_counts,
                    "recommendation": "Сбросьте статусы failed целей или добавьте новую аудиторию"
                }
            
            return {
                "status": "ready_to_execute",
                "details": "Задача готова к выполнению",
                "target_count": target_count,
                "pending_targets": pending_count,
                "status_breakdown": status_counts
            }
    
    async def diagnose_parsing_integration(self, user_id: int) -> Dict[str, Any]:
        """Диагностика интеграции с Parsing Service"""
        
        try:
            # Проверка JWT токена
            token = await self._get_jwt_token_for_parsing_service()
            
            parsing_service_url = "http://parsing-service:8000"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Проверка доступности сервиса
                try:
                    health_response = await client.get(f"{parsing_service_url}/health")
                    if health_response.status_code != 200:
                        return {
                            "issue": "parsing_service_unhealthy",
                            "details": f"Parsing service health check failed: {health_response.status_code}",
                            "response": health_response.text
                        }
                except Exception as e:
                    return {
                        "issue": "parsing_service_unreachable",
                        "details": f"Cannot connect to parsing service: {str(e)}"
                    }
                
                # Проверка аутентификации
                try:
                    tasks_response = await client.get(
                        f"{parsing_service_url}/tasks",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    
                    if tasks_response.status_code == 401:
                        return {
                            "issue": "authentication_failed",
                            "details": "JWT token rejected by parsing service"
                        }
                    elif tasks_response.status_code != 200:
                        return {
                            "issue": "api_error",
                            "details": f"Parsing service API error: {tasks_response.status_code}",
                            "response": tasks_response.text
                        }
                    
                    # Проверка задач пользователя
                    tasks_data = tasks_response.json()
                    user_tasks = [task for task in tasks_data.get('tasks', []) 
                                 if task.get('user_id') == user_id]
                    
                    return {
                        "status": "integration_working",
                        "details": "Интеграция с Parsing Service работает",
                        "total_tasks": len(tasks_data.get('tasks', [])),
                        "user_tasks": len(user_tasks),
                        "sample_tasks": user_tasks[:3]  # Первые 3 задачи
                    }
                    
                except Exception as e:
                    return {
                        "issue": "api_communication_error",
                        "details": f"Error communicating with parsing service: {str(e)}"
                    }
                    
        except Exception as e:
            return {
                "issue": "token_generation_failed",
                "details": f"Failed to generate JWT token: {str(e)}"
            }
    
    async def diagnose_file_import_issue(self, task_id: int, user_id: int) -> Dict[str, Any]:
        """Диагностика проблем с импортом файлов"""
        
        with get_db_session() as db:
            task = db.query(InviteTask).filter(
                InviteTask.id == task_id,
                InviteTask.user_id == user_id
            ).first()
            
            if not task:
                return {
                    "issue": "task_not_found",
                    "details": f"Задача {task_id} не найдена"
                }
            
            # Проверка импортированных файлов
            file_targets = db.query(InviteTarget).filter(
                InviteTarget.task_id == task_id,
                InviteTarget.source == "file_import"
            ).all()
            
            parsing_targets = db.query(InviteTarget).filter(
                InviteTarget.task_id == task_id,
                InviteTarget.source == "parsing_import"
            ).all()
            
            total_targets = db.query(InviteTarget).filter(
                InviteTarget.task_id == task_id
            ).count()
            
            # Анализ качества данных
            targets_with_username = db.query(InviteTarget).filter(
                InviteTarget.task_id == task_id,
                InviteTarget.username.isnot(None)
            ).count()
            
            targets_with_phone = db.query(InviteTarget).filter(
                InviteTarget.task_id == task_id,
                InviteTarget.phone_number.isnot(None)
            ).count()
            
            targets_with_id = db.query(InviteTarget).filter(
                InviteTarget.task_id == task_id,
                InviteTarget.user_id_platform.isnot(None)
            ).count()
            
            return {
                "status": "file_import_analysis",
                "task_info": {
                    "id": task_id,
                    "status": task.status.value,
                    "target_count_field": task.target_count,
                    "real_target_count": total_targets
                },
                "import_sources": {
                    "file_imports": len(file_targets),
                    "parsing_imports": len(parsing_targets),
                    "total": total_targets
                },
                "data_quality": {
                    "with_username": targets_with_username,
                    "with_phone": targets_with_phone,
                    "with_platform_id": targets_with_id,
                    "no_identifiers": total_targets - max(targets_with_username, targets_with_phone, targets_with_id)
                },
                "sample_targets": [
                    {
                        "id": target.id,
                        "username": target.username,
                        "phone": target.phone_number,
                        "source": target.source,
                        "status": target.status.value
                    }
                    for target in db.query(InviteTarget).filter(
                        InviteTarget.task_id == task_id
                    ).limit(5).all()
                ]
            }
    
    async def fix_task_target_count(self, task_id: int, user_id: int) -> Dict[str, Any]:
        """Исправление счетчика целей в задаче"""
        
        with get_db_session() as db:
            task = db.query(InviteTask).filter(
                InviteTask.id == task_id,
                InviteTask.user_id == user_id
            ).first()
            
            if not task:
                return {
                    "success": False,
                    "details": f"Задача {task_id} не найдена"
                }
            
            # Подсчет реального количества целей
            real_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count()
            old_count = task.target_count
            
            # Обновление счетчика
            task.target_count = real_count
            task.updated_at = datetime.utcnow()
            
            try:
                db.commit()
                
                return {
                    "success": True,
                    "details": f"Счетчик целей обновлен с {old_count} на {real_count}",
                    "old_count": old_count,
                    "new_count": real_count
                }
            except Exception as e:
                db.rollback()
                return {
                    "success": False,
                    "details": f"Ошибка обновления: {str(e)}"
                }
    
    async def _get_jwt_token_for_parsing_service(self) -> str:
        """Получение JWT токена для Parsing Service"""
        try:
            from app.core.vault import get_vault_client
            
            vault_client = get_vault_client()
            secret_data = vault_client.get_secret("jwt")
            
            if not secret_data or 'secret_key' not in secret_data:
                raise Exception("JWT secret not found in Vault")
            
            payload = {
                'service': 'invite-service',
                'user_id': 1,
                'exp': int((datetime.utcnow() + timedelta(hours=1)).timestamp())
            }
            
            token = jwt.encode(payload, secret_data['secret_key'], algorithm='HS256')
            return token
            
        except Exception as e:
            self.logger.error(f"Error getting JWT token: {e}")
            raise


# Экземпляр для использования
diagnostics = InviteServiceDiagnostics() 