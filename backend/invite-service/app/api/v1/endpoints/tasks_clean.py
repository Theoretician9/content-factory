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
from app.models import InviteTask, TaskStatus, TaskPriority
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

router = APIRouter()


def get_current_user_id() -> int:
    """Получение ID текущего пользователя из JWT токена"""
    return 1


def apply_task_filters(query, filters: TaskFilterSchema, user_id: int):
    """Применение фильтров к запросу задач"""
    query = query.filter(InviteTask.user_id == user_id)
    
    if filters.status:
        query = query.filter(InviteTask.status.in_(filters.status))
    
    if filters.platform:
        query = query.filter(InviteTask.platform.in_(filters.platform))
    
    if filters.priority:
        query = query.filter(InviteTask.priority.in_(filters.priority))
    
    if filters.created_after:
        query = query.filter(InviteTask.created_at >= filters.created_after)
    
    if filters.created_before:
        query = query.filter(InviteTask.created_at <= filters.created_before)
    
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
    else:
        return query.order_by(desc(InviteTask.created_at))


@router.post("/", response_model=InviteTaskResponse)
async def create_invite_task(
    task_data: InviteTaskCreate,
    db: Session = Depends(get_db)
):
    """Создание новой задачи приглашений"""
    user_id = get_current_user_id()
    
    try:
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
    status: Optional[List[TaskStatus]] = Query(None, description="Фильтр по статусам"),
    platform: Optional[List[str]] = Query(None, description="Фильтр по платформам"),
    priority: Optional[List[TaskPriority]] = Query(None, description="Фильтр по приоритетам"),
    created_after: Optional[datetime] = Query(None, description="Созданы после даты"),
    created_before: Optional[datetime] = Query(None, description="Созданы до даты"),
    name_contains: Optional[str] = Query(None, description="Поиск по названию"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    sort_by: TaskSortBy = Query(TaskSortBy.CREATED_AT, description="Поле для сортировки"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Порядок сортировки"),
    db: Session = Depends(get_db)
):
    """Получение списка задач приглашений с фильтрацией и пагинацией"""
    user_id = get_current_user_id()
    
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
    
    query = db.query(InviteTask)
    query = apply_task_filters(query, filters, user_id)
    
    total = query.count()
    
    query = apply_task_sorting(query, sort_by, sort_order)
    
    offset = (page - 1) * page_size
    tasks = query.offset(offset).limit(page_size).all()
    
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
    db: Session = Depends(get_db)
):
    """Получение конкретной задачи приглашений"""
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
    
    return task


@router.put("/{task_id}", response_model=InviteTaskResponse)
async def update_invite_task(
    task_id: int,
    task_update: InviteTaskUpdate,
    db: Session = Depends(get_db)
):
    """Полное обновление задачи приглашений"""
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
    
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "settings" and value is not None:
            setattr(task, field, value.dict() if hasattr(value, 'dict') else value)
        else:
            setattr(task, field, value)
    
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


@router.delete("/{task_id}")
async def delete_invite_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Удаление задачи приглашений"""
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
        db.delete(task)
        db.commit()
        return {"message": f"Задача {task_id} успешно удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления задачи: {str(e)}"
        ) 