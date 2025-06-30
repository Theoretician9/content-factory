"""
API endpoints для выполнения задач приглашений
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import asyncio

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.models import InviteTask, InviteTarget, TaskStatus, TargetStatus

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{task_id}/execute")
async def execute_invite_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Запуск выполнения задачи приглашений"""
    user_id = get_current_user_id()
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    # Проверка статуса задачи
    if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Задача не может быть запущена со статусом {task.status}"
        )
    
    # Проверка наличия целевой аудитории
    target_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count()
    
    logger.info(f"Задача {task_id}: найдено {target_count} целей для выполнения")
    
    if target_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно запустить задачу без целевой аудитории"
        )
    
    try:
        # Импорт Celery задачи
        from workers.invite_worker import execute_invite_task as celery_execute_task
        
        # Запуск асинхронной задачи через Celery
        result = celery_execute_task.delay(task_id)
        
        # Обновление статуса задачи
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "message": f"Задача {task_id} запущена в выполнение",
            "task_id": task_id,
            "celery_task_id": result.id,
            "status": "running",
            "started_at": task.start_time.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запуска задачи: {str(e)}"
        )


@router.post("/{task_id}/pause")
async def pause_invite_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Приостановка выполнения задачи"""
    user_id = get_current_user_id()
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    if task.status != TaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Задача не может быть приостановлена со статусом {task.status}"
        )
    
    try:
        # Обновление статуса
        task.status = TaskStatus.PAUSED
        task.updated_at = datetime.utcnow()
        db.commit()
        
        # TODO: Интеграция с Celery для остановки активных задач
        
        return {
            "message": f"Задача {task_id} приостановлена",
            "task_id": task_id,
            "status": "paused"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка приостановки задачи: {str(e)}"
        )


@router.post("/{task_id}/resume")
async def resume_invite_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Возобновление выполнения задачи"""
    user_id = get_current_user_id()
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    if task.status != TaskStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Задача не может быть возобновлена со статусом {task.status}"
        )
    
    try:
        # Импорт Celery задачи
        from workers.invite_worker import execute_invite_task as celery_execute_task
        
        # Перезапуск задачи
        result = celery_execute_task.delay(task_id)
        
        # Обновление статуса
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "message": f"Задача {task_id} возобновлена",
            "task_id": task_id,
            "celery_task_id": result.id,
            "status": "running"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка возобновления задачи: {str(e)}"
        )


@router.post("/{task_id}/cancel")
async def cancel_invite_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Отмена выполнения задачи"""
    user_id = get_current_user_id()
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    if task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Задача не может быть отменена со статусом {task.status}"
        )
    
    try:
        # Обновление статуса
        task.status = TaskStatus.CANCELLED
        task.end_time = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.commit()
        
        # TODO: Интеграция с Celery для отмены активных задач
        
        return {
            "message": f"Задача {task_id} отменена",
            "task_id": task_id,
            "status": "cancelled"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отмены задачи: {str(e)}"
        )


@router.get("/{task_id}/status")
async def get_task_status(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Получение детального статуса выполнения задачи"""
    user_id = get_current_user_id()
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    # Получение статистики по целям
    targets_stats = db.query(
        InviteTarget.status,
        func.count(InviteTarget.id).label('count')
    ).filter(
        InviteTarget.task_id == task_id
    ).group_by(InviteTarget.status).all()
    
    # Преобразование в словарь
    status_counts = {status.value: 0 for status in TargetStatus}
    for stat in targets_stats:
        status_counts[stat.status.value] = stat.count
    
    # Вычисление процента выполнения
    total_targets = sum(status_counts.values())
    completed_targets = status_counts.get('invited', 0) + status_counts.get('failed', 0)
    progress_percentage = (completed_targets / total_targets * 100) if total_targets > 0 else 0
    
    # Время выполнения
    execution_time = None
    if task.start_time:
        end_time = task.end_time or datetime.utcnow()
        execution_time = (end_time - task.start_time).total_seconds()
    
    return {
        "task_id": task_id,
        "status": task.status.value,
        "progress_percentage": round(progress_percentage, 2),
        "targets": {
            "total": total_targets,
            "pending": status_counts.get('pending', 0),
            "invited": status_counts.get('invited', 0),
            "failed": status_counts.get('failed', 0)
        },
        "timing": {
            "created_at": task.created_at.isoformat(),
            "started_at": task.start_time.isoformat() if task.start_time else None,
            "ended_at": task.end_time.isoformat() if task.end_time else None,
            "execution_time_seconds": execution_time
        },
        "settings": task.settings,
        "error_message": task.error_message
    }


@router.get("/{task_id}/accounts")
async def get_task_available_accounts(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Получение доступных аккаунтов для выполнения задачи"""
    user_id = get_current_user_id()
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    try:
        # Получение адаптера платформы
        from app.adapters.factory import get_platform_adapter
        
        adapter = get_platform_adapter(task.platform)
        
        # Асинхронная инициализация аккаунтов
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            accounts = loop.run_until_complete(adapter.initialize_accounts(user_id))
        finally:
            loop.close()
        
        # Получение rate limiting информации
        from app.utils.rate_limiter import get_rate_limiter
        rate_limiter = get_rate_limiter()
        
        account_info = []
        for account in accounts:
            # Получение текущего использования
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                usage = loop.run_until_complete(rate_limiter.get_account_usage(account))
                can_invite = loop.run_until_complete(rate_limiter.can_send_invite(account))
            finally:
                loop.close()
            
            account_info.append({
                "account_id": account.account_id,
                "username": account.username,
                "phone": account.phone,
                "status": account.status.value,
                "platform": account.platform,
                "limits": {
                    "daily_invite_limit": account.daily_invite_limit,
                    "daily_message_limit": account.daily_message_limit,
                    "hourly_invite_limit": account.hourly_invite_limit
                },
                "usage": usage,
                "can_send_invite": can_invite,
                "flood_wait_until": account.flood_wait_until.isoformat() if account.flood_wait_until else None
            })
        
        return {
            "task_id": task_id,
            "platform": task.platform,
            "total_accounts": len(accounts),
            "active_accounts": len([acc for acc in accounts if acc.status.value == 'active']),
            "accounts": account_info
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения аккаунтов: {str(e)}"
        )


@router.post("/{task_id}/test-invite")
async def test_single_invite(
    task_id: int,
    target_id: int,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Тестовая отправка одного приглашения"""
    user_id = get_current_user_id()
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    # Проверка существования цели
    target = db.query(InviteTarget).filter(
        InviteTarget.id == target_id,
        InviteTarget.task_id == task_id
    ).first()
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Цель с ID {target_id} не найдена в задаче {task_id}"
        )
    
    try:
        # Импорт Celery задачи
        from workers.invite_worker import single_invite_operation
        
        # Запуск тестового приглашения
        result = single_invite_operation.delay(task_id, target_id, account_id)
        
        return {
            "message": "Тестовое приглашение запущено",
            "task_id": task_id,
            "target_id": target_id,
            "account_id": account_id,
            "celery_task_id": result.id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки тестового приглашения: {str(e)}"
        ) 