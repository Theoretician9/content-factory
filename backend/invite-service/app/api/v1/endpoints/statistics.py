from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func, text
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from app.core.database import get_db
from app.models.invite_task import InviteTask, TaskStatus
from app.models.invite_target import InviteTarget, TargetStatus
from app.models.invite_execution_log import InviteExecutionLog, ExecutionResult
from app.core.auth import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/tasks/{task_id}/stats")
async def get_task_stats(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Получение детальной статистики по задаче приглашений
    """
    # Проверяем доступ к задаче
    task_query = select(InviteTask).where(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    )
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Базовая статистика по целям
    targets_stats_query = select(
        func.count(InviteTarget.id).label('total_targets'),
        func.count(InviteTarget.id).filter(InviteTarget.status == TargetStatus.PENDING).label('pending_targets'),
        func.count(InviteTarget.id).filter(InviteTarget.status == TargetStatus.INVITED).label('invited_targets'),
        func.count(InviteTarget.id).filter(InviteTarget.status == TargetStatus.FAILED).label('failed_targets'),
        func.count(InviteTarget.id).filter(InviteTarget.status == TargetStatus.SKIPPED).label('skipped_targets'),
    ).where(InviteTarget.task_id == task_id)
    
    targets_stats_result = await db.execute(targets_stats_query)
    targets_stats = targets_stats_result.first()
    
    # Статистика по результатам выполнения из логов
    execution_stats_query = select(
        func.count(InviteExecutionLog.id).label('total_attempts'),
        func.count(InviteExecutionLog.id).filter(InviteExecutionLog.result == ExecutionResult.SUCCESS).label('successful_invites'),
        func.count(InviteExecutionLog.id).filter(InviteExecutionLog.result == ExecutionResult.FAILED).label('failed_invites'),
        func.count(InviteExecutionLog.id).filter(InviteExecutionLog.result == ExecutionResult.RATE_LIMITED).label('rate_limited'),
        func.count(InviteExecutionLog.id).filter(InviteExecutionLog.result == ExecutionResult.FLOOD_WAIT).label('flood_wait'),
        func.avg(InviteExecutionLog.execution_time).label('avg_execution_time')
    ).where(InviteExecutionLog.task_id == task_id)
    
    execution_stats_result = await db.execute(execution_stats_query)
    execution_stats = execution_stats_result.first()
    
    # Статистика по времени выполнения
    time_stats_query = select(
        func.min(InviteExecutionLog.created_at).label('first_execution'),
        func.max(InviteExecutionLog.created_at).label('last_execution'),
    ).where(InviteExecutionLog.task_id == task_id)
    
    time_stats_result = await db.execute(time_stats_query)
    time_stats = time_stats_result.first()
    
    # Рассчитываем процент выполнения
    total_targets = targets_stats.total_targets or 0
    completed_targets = (targets_stats.invited_targets or 0) + (targets_stats.failed_targets or 0) + (targets_stats.skipped_targets or 0)
    progress_percentage = (completed_targets / total_targets * 100) if total_targets > 0 else 0
    
    # Успешность в процентах
    success_rate = ((targets_stats.invited_targets or 0) / total_targets * 100) if total_targets > 0 else 0
    
    return {
        "task_id": task_id,
        "task_name": task.name,
        "task_status": task.status,
        "task_platform": task.platform,
        "task_priority": task.priority,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "targets_statistics": {
            "total_targets": total_targets,
            "pending_targets": targets_stats.pending_targets or 0,
            "invited_targets": targets_stats.invited_targets or 0,
            "failed_targets": targets_stats.failed_targets or 0,
            "skipped_targets": targets_stats.skipped_targets or 0,
            "progress_percentage": round(progress_percentage, 2),
            "success_rate": round(success_rate, 2)
        },
        "execution_statistics": {
            "total_attempts": execution_stats.total_attempts or 0,
            "successful_invites": execution_stats.successful_invites or 0,
            "failed_invites": execution_stats.failed_invites or 0,
            "rate_limited": execution_stats.rate_limited or 0,
            "flood_wait": execution_stats.flood_wait or 0,
            "avg_execution_time": round(float(execution_stats.avg_execution_time or 0), 3)
        },
        "time_statistics": {
            "first_execution": time_stats.first_execution,
            "last_execution": time_stats.last_execution,
            "total_duration": (time_stats.last_execution - time_stats.first_execution).total_seconds() if time_stats.first_execution and time_stats.last_execution else 0
        }
    }

@router.get("/tasks/{task_id}/report")
async def get_task_report(
    task_id: int,
    include_logs: bool = Query(False, description="Include detailed execution logs"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Получение финального отчета по выполнению задачи
    """
    # Проверяем доступ к задаче
    task_query = select(InviteTask).where(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    )
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Получаем статистику (переиспользуем логику из /stats)
    stats_data = await get_task_stats(task_id, db, user_id)
    
    # Дополнительная информация для отчета
    report_data = {
        **stats_data,
        "report_generated_at": datetime.utcnow(),
        "task_settings": {
            "message_template": task.message_template,
            "invite_type": task.invite_type,
            "batch_size": task.batch_size,
            "delay_between_invites": task.delay_between_invites
        }
    }
    
    # Включаем детальные логи если запрошено
    if include_logs:
        logs_query = select(InviteExecutionLog).where(
            InviteExecutionLog.task_id == task_id
        ).order_by(InviteExecutionLog.created_at.desc()).limit(100)
        
        logs_result = await db.execute(logs_query)
        logs = logs_result.scalars().all()
        
        report_data["execution_logs"] = [
            {
                "id": log.id,
                "target_id": log.target_id,
                "account_id": log.account_id,
                "result": log.result,
                "error_message": log.error_message,
                "execution_time": log.execution_time,
                "created_at": log.created_at
            }
            for log in logs
        ]
    
    return report_data

@router.get("/tasks/{task_id}/logs")
async def get_task_logs(
    task_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    result_filter: Optional[ExecutionResult] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Получение логов выполнения задачи с пагинацией
    """
    # Проверяем доступ к задаче
    task_query = select(InviteTask).where(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    )
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Базовый запрос логов
    logs_query = select(InviteExecutionLog).where(
        InviteExecutionLog.task_id == task_id
    )
    
    # Фильтрация по результату если указан
    if result_filter:
        logs_query = logs_query.where(InviteExecutionLog.result == result_filter)
    
    # Подсчет общего количества
    count_query = select(func.count(InviteExecutionLog.id)).where(
        InviteExecutionLog.task_id == task_id
    )
    if result_filter:
        count_query = count_query.where(InviteExecutionLog.result == result_filter)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Пагинация
    offset = (page - 1) * page_size
    logs_query = logs_query.order_by(InviteExecutionLog.created_at.desc()).offset(offset).limit(page_size)
    
    logs_result = await db.execute(logs_query)
    logs = logs_result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "logs": [
            {
                "id": log.id,
                "target_id": log.target_id,
                "account_id": log.account_id,
                "result": log.result,
                "error_message": log.error_message,
                "execution_time": log.execution_time,
                "created_at": log.created_at,
                "metadata": log.metadata
            }
            for log in logs
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "filter": {
            "result_filter": result_filter
        }
    }

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Получение общей сводки для dashboard пользователя
    """
    # Статистика по задачам
    tasks_stats_query = select(
        func.count(InviteTask.id).label('total_tasks'),
        func.count(InviteTask.id).filter(InviteTask.status == TaskStatus.PENDING).label('pending_tasks'),
        func.count(InviteTask.id).filter(InviteTask.status == TaskStatus.RUNNING).label('running_tasks'),
        func.count(InviteTask.id).filter(InviteTask.status == TaskStatus.COMPLETED).label('completed_tasks'),
        func.count(InviteTask.id).filter(InviteTask.status == TaskStatus.FAILED).label('failed_tasks'),
    ).where(InviteTask.user_id == user_id)
    
    tasks_stats_result = await db.execute(tasks_stats_query)
    tasks_stats = tasks_stats_result.first()
    
    # Общая статистика по приглашениям за последние 30 дней
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    invites_stats_query = select(
        func.count(InviteExecutionLog.id).label('total_invites'),
        func.count(InviteExecutionLog.id).filter(InviteExecutionLog.result == ExecutionResult.SUCCESS).label('successful_invites'),
        func.count(InviteExecutionLog.id).filter(InviteExecutionLog.result == ExecutionResult.FAILED).label('failed_invites'),
    ).join(InviteTask, InviteExecutionLog.task_id == InviteTask.id).where(
        InviteTask.user_id == user_id,
        InviteExecutionLog.created_at >= thirty_days_ago
    )
    
    invites_stats_result = await db.execute(invites_stats_query)
    invites_stats = invites_stats_result.first()
    
    # Последние активные задачи
    recent_tasks_query = select(InviteTask).where(
        InviteTask.user_id == user_id
    ).order_by(InviteTask.updated_at.desc()).limit(5)
    
    recent_tasks_result = await db.execute(recent_tasks_query)
    recent_tasks = recent_tasks_result.scalars().all()
    
    success_rate = 0
    if invites_stats.total_invites and invites_stats.total_invites > 0:
        success_rate = (invites_stats.successful_invites / invites_stats.total_invites * 100)
    
    return {
        "tasks_summary": {
            "total_tasks": tasks_stats.total_tasks or 0,
            "pending_tasks": tasks_stats.pending_tasks or 0,
            "running_tasks": tasks_stats.running_tasks or 0,
            "completed_tasks": tasks_stats.completed_tasks or 0,
            "failed_tasks": tasks_stats.failed_tasks or 0
        },
        "invites_summary": {
            "total_invites_30d": invites_stats.total_invites or 0,
            "successful_invites_30d": invites_stats.successful_invites or 0,
            "failed_invites_30d": invites_stats.failed_invites or 0,
            "success_rate_30d": round(success_rate, 2)
        },
        "recent_tasks": [
            {
                "id": task.id,
                "name": task.name,
                "status": task.status,
                "platform": task.platform,
                "target_count": task.target_count,
                "created_at": task.created_at,
                "updated_at": task.updated_at
            }
            for task in recent_tasks
        ],
        "generated_at": datetime.utcnow()
    } 