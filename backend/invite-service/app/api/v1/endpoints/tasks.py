"""
API endpoints для управления задачами приглашений
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional
from datetime import datetime
import math

from app.core.database import get_db
from app.models import InviteTask, TaskStatus
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


@router.post("/", response_model=InviteTaskResponse)
async def create_invite_task(
    task_data: InviteTaskCreate,
    db: Session = Depends(get_db)
):
    """Создание новой задачи приглашений"""
    # TODO: Добавить JWT авторизацию и получение user_id из токена
    user_id = 1  # Заглушка
    
    try:
        # Создание новой задачи
        task = InviteTask(
            user_id=user_id,
            name=task_data.name,
            description=task_data.description,
            platform=task_data.platform,
            delay_between_invites=task_data.delay_between_invites,
            max_invites_per_account=task_data.max_invites_per_account,
            invite_message=task_data.invite_message,
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


@router.get("/", response_model=List[InviteTaskResponse])
async def get_invite_tasks(
    skip: int = 0,
    limit: int = 100,
    status_filter: TaskStatus = None,
    db: Session = Depends(get_db)
):
    """Получение списка задач приглашений"""
    # TODO: Добавить JWT авторизацию и фильтрацию по user_id
    user_id = 1  # Заглушка
    
    query = db.query(InviteTask).filter(InviteTask.user_id == user_id)
    
    if status_filter:
        query = query.filter(InviteTask.status == status_filter)
    
    tasks = query.offset(skip).limit(limit).all()
    return tasks


@router.get("/{task_id}", response_model=InviteTaskResponse)
async def get_invite_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Получение конкретной задачи приглашений"""
    # TODO: Добавить JWT авторизацию и проверку владельца
    
    task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
    
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
    """Обновление задачи приглашений"""
    # TODO: Добавить JWT авторизацию и проверку владельца
    
    task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    # Обновление полей
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
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
    # TODO: Добавить JWT авторизацию и проверку владельца
    
    task = db.query(InviteTask).filter(InviteTask.id == task_id).first()
    
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