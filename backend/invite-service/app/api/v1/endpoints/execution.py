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
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Запуск выполнения задачи приглашений"""
    
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

        # Обновление статуса задачи (сохраняем строковое значение для совместимости с БД)
        task.status = TaskStatus.RUNNING.value
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
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Приостановка выполнения задачи"""
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )

    if str(task.status) != TaskStatus.RUNNING.value and task.status != TaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Задача не может быть приостановлена со статусом {task.status}"
        )

    try:
        # Обновляем статус, сохраняя строковое значение
        task.status = TaskStatus.PAUSED.value
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
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Возобновление выполнения задачи"""
    
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

        # Обновляем статус, сохраняя строковое значение
        task.status = TaskStatus.RUNNING.value
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
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Отмена выполнения задачи"""
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )

    if (
        str(task.status) not in [TaskStatus.RUNNING.value, TaskStatus.PAUSED.value, TaskStatus.PENDING.value]
        and task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.PENDING]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Задача не может быть отменена со статусом {task.status}"
        )

    try:
        # Обновляем статус, сохраняя строковое значение
        task.status = TaskStatus.CANCELLED.value
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
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Получение детального статуса выполнения задачи"""
    
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
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Получение доступных аккаунтов для выполнения задачи"""
    
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
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Тестовая отправка одного приглашения"""
    
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


@router.get("/{task_id}/diagnose")
async def diagnose_task_issues(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Диагностика проблем с задачей инвайтинга"""
    
    # Проверка существования задачи
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()

    if not task:
        return {
            "issue": "task_not_found",
            "details": f"Задача {task_id} не найдена для пользователя {user_id}",
            "recommendations": ["Проверьте правильность ID задачи", "Убедитесь что задача принадлежит вашему пользователю"]
        }

    # Получение реального количества целей
    real_target_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count()

    # Статистика по целям
    target_stats = db.query(
        InviteTarget.status,
        func.count(InviteTarget.id).label('count')
    ).filter(
        InviteTarget.task_id == task_id
    ).group_by(InviteTarget.status).all()

    status_counts = {stat.status.value: stat.count for stat in target_stats}
    pending_count = status_counts.get('pending', 0)

    # Анализ проблем
    issues = []
    recommendations = []

    # Проблема 1: Нет целей
    if real_target_count == 0:
        issues.append("no_targets")
        recommendations.extend([
            "Загрузите аудиторию через файл (CSV/JSON/TXT)",
            "Импортируйте аудиторию из результатов парсинга",
            "Проверьте что файл был загружен корректно"
        ])

    # Проблема 2: Несоответствие счетчиков
    if task.target_count != real_target_count:
        issues.append("count_mismatch")
        recommendations.append(f"Исправьте счетчик: task.target_count={task.target_count}, реально={real_target_count}")

    # Проблема 3: Нет pending целей
    if real_target_count > 0 and pending_count == 0:
        issues.append("no_pending_targets")
        recommendations.extend([
            "Сбросьте статусы failed целей на pending",
            "Добавьте новую аудиторию",
            "Проверьте что цели не были обработаны ранее"
        ])

    # Проблема 4: Неправильный статус задачи
    if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
        issues.append("invalid_task_status")
        recommendations.append(f"Задача в статусе {task.status.value}, должна быть PENDING или PAUSED")

    # Анализ качества данных
    data_quality = {}
    if real_target_count > 0:
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

        data_quality = {
            "with_username": targets_with_username,
            "with_phone": targets_with_phone,
            "with_platform_id": targets_with_id,
            "percentage_with_identifiers": round((max(targets_with_username, targets_with_phone, targets_with_id) / real_target_count) * 100, 2)
        }

        if data_quality["percentage_with_identifiers"] < 50:
            issues.append("poor_data_quality")
            recommendations.append("Низкое качество данных - проверьте формат загружаемых файлов")

    # Общий статус
    if not issues:
        overall_status = "ready_to_execute"
        overall_message = "Задача готова к выполнению"
    else:
        overall_status = "has_issues"
        overall_message = f"Обнаружено проблем: {len(issues)}"

    return {
        "task_id": task_id,
        "overall_status": overall_status,
        "overall_message": overall_message,
        "issues": issues,
        "recommendations": recommendations,
        "task_info": {
            "status": task.status.value,
            "target_count_field": task.target_count,
            "real_target_count": real_target_count,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        },
        "target_statistics": {
            "total": real_target_count,
            "status_breakdown": status_counts,
            "pending_targets": pending_count
        },
        "data_quality": data_quality
    }


@router.post("/{task_id}/fix-count")
async def fix_task_target_count(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Исправление счетчика целей в задаче"""
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )

    # Подсчет реального количества целей
    real_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count()
    old_count = task.target_count

    # Обновление счетчика
    task.target_count = real_count
    task.updated_at = datetime.utcnow()

    try:
        db.commit()

        logger.info(f"Исправлен счетчик целей для задачи {task_id}: {old_count} -> {real_count}")

        return {
            "message": f"Счетчик целей обновлен с {old_count} на {real_count}",
            "task_id": task_id,
            "old_count": old_count,
            "new_count": real_count,
            "fixed": True
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка исправления счетчика для задачи {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления счетчика: {str(e)}"
        ) 