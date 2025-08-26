"""
API endpoints для управления задачами приглашений
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from typing import List, Optional
from datetime import datetime
import math

from app.core.database import get_db
from app.models import InviteTask, TaskStatus, TaskPriority, InviteTarget, TargetStatus
from app.schemas.invite_task import (
    InviteTaskCreate, 
    InviteTaskResponse, 
    InviteTaskUpdate,
    TaskFilterSchema,
    TaskListResponse,
    TaskDuplicateRequest,
    TaskBulkRequest,
    TaskBulkAction,
    TaskSortBy,
    SortOrder
)
from app.core.auth import get_current_user_id

router = APIRouter()


def apply_task_filters(query, filters: TaskFilterSchema, user_id: int):
    """Применение фильтров к запросу задач"""
    # Базовая фильтрация по пользователю
    query = query.filter(InviteTask.user_id == user_id)
    
    # Фильтр по статусам
    if filters.status:
        query = query.filter(InviteTask.status.in_(filters.status))
    
    # Фильтр по платформам
    if filters.platform:
        query = query.filter(InviteTask.platform.in_(filters.platform))
    
    # Фильтр по приоритетам
    if filters.priority:
        query = query.filter(InviteTask.priority.in_(filters.priority))
    
    # Фильтр по датам создания
    if filters.created_after:
        query = query.filter(InviteTask.created_at >= filters.created_after)
    
    if filters.created_before:
        query = query.filter(InviteTask.created_at <= filters.created_before)
    
    # Поиск по названию
    if filters.name_contains:
        query = query.filter(InviteTask.name.ilike(f"%{filters.name_contains}%"))
    
    return query


def apply_task_sorting(query, sort_by: TaskSortBy, sort_order: SortOrder):
    """Применение сортировки к запросу задач"""
    order_func = desc if sort_order == SortOrder.DESC else asc
    
    if sort_by == TaskSortBy.CREATED_AT:
        return query.order_by(order_func(InviteTask.created_at))
    elif sort_by == TaskSortBy.UPDATED_AT:
        return query.order_by(order_func(InviteTask.updated_at))
    elif sort_by == TaskSortBy.NAME:
        return query.order_by(order_func(InviteTask.name))
    elif sort_by == TaskSortBy.PRIORITY:
        return query.order_by(order_func(InviteTask.priority))
    elif sort_by == TaskSortBy.STATUS:
        return query.order_by(order_func(InviteTask.status))
    elif sort_by == TaskSortBy.PROGRESS:
        # Вычисленное поле прогресса
        progress = func.coalesce(
            (InviteTask.completed_count + InviteTask.failed_count) * 100.0 / 
            func.nullif(InviteTask.target_count, 0), 0
        )
        return query.order_by(order_func(progress))
    else:
        return query.order_by(desc(InviteTask.created_at))


@router.post("/", response_model=InviteTaskResponse)
async def create_invite_task(
    task_data: InviteTaskCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Создание новой задачи приглашений"""
    
    try:
        # Создание новой задачи
        task = InviteTask(
            user_id=user_id,
            name=task_data.name,
            description=task_data.description,
            platform=task_data.platform,
            priority=task_data.priority,
            delay_between_invites=task_data.delay_between_invites,
            max_invites_per_account=task_data.max_invites_per_account,
            invite_message=task_data.invite_message,
            scheduled_start=task_data.scheduled_start,
            settings=task_data.settings.dict() if task_data.settings else None
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        return task
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания задачи: {str(e)}"
        )


@router.get("/", response_model=TaskListResponse)
async def get_invite_tasks(
    # Фильтры
    status: Optional[List[TaskStatus]] = Query(None, description="Фильтр по статусам"),
    platform: Optional[List[str]] = Query(None, description="Фильтр по платформам"),
    priority: Optional[List[TaskPriority]] = Query(None, description="Фильтр по приоритетам"),
    created_after: Optional[datetime] = Query(None, description="Созданы после даты"),
    created_before: Optional[datetime] = Query(None, description="Созданы до даты"),
    name_contains: Optional[str] = Query(None, description="Поиск по названию"),
    
    # Пагинация
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    
    # Сортировка
    sort_by: TaskSortBy = Query(TaskSortBy.CREATED_AT, description="Поле для сортировки"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Порядок сортировки"),
    
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Получение списка задач приглашений с фильтрацией и пагинацией"""
    
    # Создание объекта фильтров
    filters = TaskFilterSchema(
        status=status,
        platform=platform,
        priority=priority,
        created_after=created_after,
        created_before=created_before,
        name_contains=name_contains,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    # Основной запрос
    query = db.query(InviteTask)
    
    # Применение фильтров
    query = apply_task_filters(query, filters, user_id)
    
    # Подсчет общего количества
    total = query.count()
    
    # Применение сортировки
    query = apply_task_sorting(query, sort_by, sort_order)
    
    # Применение пагинации
    offset = (page - 1) * page_size
    tasks = query.offset(offset).limit(page_size).all()
    
    # Вычисление метаданных пагинации
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    has_next = page < total_pages
    has_prev = page > 1
    
    return TaskListResponse(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/{task_id}", response_model=InviteTaskResponse)
async def get_invite_task(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Получение конкретной задачи приглашений"""
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id  # Проверка владельца
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    return task


@router.put("/{task_id}", response_model=InviteTaskResponse)
async def update_invite_task(
    task_id: int,
    task_update: InviteTaskUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Полное обновление задачи приглашений"""
    
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    # Обновление полей
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "settings" and value is not None:
            # Специальная обработка для JSON полей
            setattr(task, field, value.dict() if hasattr(value, 'dict') else value)
        else:
            setattr(task, field, value)
    
    # Обновление времени изменения
    task.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(task)
        return task
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления задачи: {str(e)}"
        )


@router.post("/{task_id}/duplicate", response_model=InviteTaskResponse)
async def duplicate_invite_task(
    task_id: int,
    duplicate_data: TaskDuplicateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Дублирование задачи приглашений"""
    
    # Получение оригинальной задачи
    original_task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not original_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    try:
        # Создание копии задачи
        new_task = InviteTask(
            user_id=user_id,
            name=duplicate_data.new_name,
            description=f"Копия: {original_task.description}" if original_task.description else None,
            platform=original_task.platform,
            priority=original_task.priority,
            delay_between_invites=original_task.delay_between_invites,
            max_invites_per_account=original_task.max_invites_per_account,
            invite_message=original_task.invite_message,
            settings=original_task.settings if duplicate_data.copy_settings else None,
            scheduled_start=None if duplicate_data.reset_schedule else original_task.scheduled_start,
            status=TaskStatus.PENDING  # Новая задача всегда pending
        )
        
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        # TODO: Копирование целевой аудитории если copy_targets=True
        # Это будет реализовано при создании endpoints для targets
        
        return new_task
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка дублирования задачи: {str(e)}"
        )


@router.post("/bulk", response_model=dict)
async def bulk_task_operations(
    bulk_request: TaskBulkRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Массовые операции с задачами"""
    
    # Проверка существования всех задач и прав доступа
    tasks = db.query(InviteTask).filter(
        InviteTask.id.in_(bulk_request.task_ids),
        InviteTask.user_id == user_id
    ).all()
    
    if len(tasks) != len(bulk_request.task_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Некоторые задачи не найдены или нет доступа"
        )
    
    try:
        affected_count = 0
        
        if bulk_request.action == TaskBulkAction.DELETE:
            # Удаление задач
            for task in tasks:
                db.delete(task)
                affected_count += 1
                
        elif bulk_request.action == TaskBulkAction.PAUSE:
            # Приостановка задач
            for task in tasks:
                if task.status in [TaskStatus.RUNNING, TaskStatus.PENDING]:
                    task.status = TaskStatus.PAUSED
                    affected_count += 1
                    
        elif bulk_request.action == TaskBulkAction.RESUME:
            # Возобновление задач
            for task in tasks:
                if task.status == TaskStatus.PAUSED:
                    task.status = TaskStatus.PENDING
                    affected_count += 1
                    
        elif bulk_request.action == TaskBulkAction.CANCEL:
            # Отмена задач
            for task in tasks:
                if task.status in [TaskStatus.RUNNING, TaskStatus.PENDING, TaskStatus.PAUSED]:
                    task.status = TaskStatus.CANCELLED
                    affected_count += 1
                    
        elif bulk_request.action == TaskBulkAction.SET_PRIORITY:
            # Установка приоритета
            new_priority = bulk_request.parameters.get("priority") if bulk_request.parameters else None
            if not new_priority or new_priority not in [p.value for p in TaskPriority]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Необходимо указать корректный приоритет в параметрах"
                )
            
            for task in tasks:
                task.priority = TaskPriority(new_priority)
                affected_count += 1
        
        # Обновление времени изменения для всех затронутых задач
        for task in tasks:
            task.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": f"Операция '{bulk_request.action}' выполнена",
            "affected_count": affected_count,
            "total_requested": len(bulk_request.task_ids)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка выполнения массовой операции: {str(e)}"
        )


@router.delete("/{task_id}")
async def delete_invite_task(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Удаление задачи приглашений"""
    
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
        db.delete(task)
        db.commit()
        return {"message": f"Задача {task_id} успешно удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления задачи: {str(e)}"
        )


# =============================================================================
# НОВЫЕ ENDPOINTS ДЛЯ ВЫПОЛНЕНИЯ ЗАДАЧ И ИНТЕГРАЦИИ С ПЛАТФОРМАМИ
# =============================================================================

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
    
    # Проверка статуса задачи - разрешаем перезапуск FAILED и IN_PROGRESS задач
    if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED, TaskStatus.FAILED, TaskStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка запуска задачи: {task.status}"
        )
    
    # Проверка наличия целевой аудитории
    target_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count()
    
    if target_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно запустить задачу без целевой аудитории"
        )
    
    try:
        # Импорт Celery задачи
        from workers.invite_worker import execute_invite_task as celery_execute_task
        
        logger.info(f"🔍 DIAGNOSTIC: About to queue Celery task for task_id={task_id}")
        
        # Запуск асинхронной задачи через Celery
        result = celery_execute_task.delay(task_id)
        
        logger.info(f"🔍 DIAGNOSTIC: Celery task queued successfully - task_id={task_id}, celery_id={result.id}")
        
        # Обновление статуса задачи (используем значение enum в БД)
        task.status = TaskStatus.IN_PROGRESS.value
        task.start_time = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"🔍 DIAGNOSTIC: Task status updated to IN_PROGRESS for task_id={task_id}")
        
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
    
    if str(task.status) != TaskStatus.IN_PROGRESS.value and task.status != TaskStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Задача не может быть приостановлена со статусом {task.status}"
        )
    
    try:
        # Обновление статуса (значение enum)
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


@router.post("/check-admin-rights")
async def check_admin_rights(
    request: dict,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Проверка администраторских прав аккаунтов в группе/канале
    """
    try:
        group_link = request.get("group_link", "").strip()
        if not group_link:
            raise HTTPException(status_code=400, detail="Не указана ссылка на группу/канал")
        
        # Получаем все активные Telegram аккаунты пользователя
        # TODO: Интеграция с integration-service для получения реальных аккаунтов
        
        # Временная заглушка с тестовыми данными
        mock_accounts = [
            {
                "account_id": "test_admin_1",
                "username": "admin_account_1",
                "status": "active",
                "is_admin": True,
                "permissions": ["invite_users", "add_admins"],
                "daily_limit": 50,
                "used_today": 12
            },
            {
                "account_id": "test_user_2", 
                "username": "regular_user_2",
                "status": "active",
                "is_admin": False,
                "permissions": [],
                "daily_limit": 30,
                "used_today": 5
            },
            {
                "account_id": "test_admin_3",
                "username": "admin_account_3", 
                "status": "rate_limited",
                "is_admin": True,
                "permissions": ["invite_users"],
                "daily_limit": 40,
                "used_today": 40,
                "rate_limit_until": "2024-01-01T15:30:00Z"
            }
        ]
        
        # Фильтруем только администраторов с правами приглашать
        admin_accounts = [
            acc for acc in mock_accounts 
            if acc["is_admin"] and "invite_users" in acc["permissions"]
        ]
        
        # Проверяем готовность к работе
        ready_accounts = []
        unavailable_accounts = []
        
        for acc in admin_accounts:
            if acc["status"] == "active" and acc["used_today"] < acc["daily_limit"]:
                ready_accounts.append({
                    "account_id": acc["account_id"],
                    "username": acc["username"],
                    "status": "ready",
                    "available_invites": acc["daily_limit"] - acc["used_today"],
                    "permissions": acc["permissions"]
                })
            else:
                unavailable_accounts.append({
                    "account_id": acc["account_id"],
                    "username": acc["username"],
                    "status": acc["status"],
                    "reason": "rate_limited" if acc["status"] == "rate_limited" else "daily_limit_reached",
                    "available_at": acc.get("rate_limit_until"),
                    "permissions": acc["permissions"]
                })
        
        # Извлекаем название группы из ссылки (упрощенно)
        group_name = group_link.split('/')[-1].replace('@', '')
        
        return {
            "group_link": group_link,
            "group_name": group_name,
            "total_accounts_checked": len(mock_accounts),
            "admin_accounts": len(admin_accounts),
            "ready_accounts": ready_accounts,
            "unavailable_accounts": unavailable_accounts,
            "can_proceed": len(ready_accounts) > 0,
            "estimated_capacity": sum(acc["available_invites"] for acc in ready_accounts)
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки админских прав: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking admin rights: {str(e)}")


# Utility functions 