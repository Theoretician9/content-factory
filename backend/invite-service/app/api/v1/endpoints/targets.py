"""
API endpoints для управления целевыми контактами (targets)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from typing import List, Optional, Dict, Any
from datetime import datetime
import math
import io
import csv
import json
import logging

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.models import InviteTarget, InviteTask, TargetStatus
from app.schemas.target import (
    InviteTargetCreate,
    InviteTargetBulkCreate,
    InviteTargetUpdate,
    InviteTargetResponse,
    TargetFilterSchema,
    TargetListResponse,
    TargetImportSchema,
    TargetImportResult,
    TargetBulkRequest,
    TargetBulkAction,
    TargetStatsResponse,
    TargetSource,
    TargetSortBy
)

logger = logging.getLogger(__name__)
router = APIRouter()


def check_task_ownership(task_id: int, user_id: int, db: Session) -> InviteTask:
    """Проверка принадлежности задачи пользователю"""
    task = db.query(InviteTask).filter(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена или нет доступа"
        )
    
    return task


def apply_target_filters(query, filters: TargetFilterSchema):
    """Применение фильтров к запросу целей"""
    # Фильтр по статусам
    if filters.status:
        query = query.filter(InviteTarget.status.in_(filters.status))
    
    # Фильтр по источникам
    if filters.source:
        query = query.filter(InviteTarget.source.in_(filters.source))
    
    # Фильтры по наличию данных
    if filters.has_username is not None:
        if filters.has_username:
            query = query.filter(InviteTarget.username.isnot(None))
        else:
            query = query.filter(InviteTarget.username.is_(None))
    
    if filters.has_phone is not None:
        if filters.has_phone:
            query = query.filter(InviteTarget.phone_number.isnot(None))
        else:
            query = query.filter(InviteTarget.phone_number.is_(None))
    
    # Фильтр по датам создания
    if filters.created_after:
        query = query.filter(InviteTarget.created_at >= filters.created_after)
    
    if filters.created_before:
        query = query.filter(InviteTarget.created_at <= filters.created_before)
    
    # Поиск по различным полям
    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.filter(
            or_(
                InviteTarget.username.ilike(search_term),
                InviteTarget.full_name.ilike(search_term),
                InviteTarget.email.ilike(search_term),
                InviteTarget.phone_number.ilike(search_term)
            )
        )
    
    return query


def apply_target_sorting(query, sort_by: TargetSortBy, sort_order: str):
    """Применение сортировки к запросу целей"""
    order_func = desc if sort_order == "desc" else asc
    
    if sort_by == TargetSortBy.CREATED_AT:
        return query.order_by(order_func(InviteTarget.created_at))
    elif sort_by == TargetSortBy.USERNAME:
        return query.order_by(order_func(InviteTarget.username))
    elif sort_by == TargetSortBy.STATUS:
        return query.order_by(order_func(InviteTarget.status))
    elif sort_by == TargetSortBy.LAST_ATTEMPT:
        return query.order_by(order_func(InviteTarget.last_attempt_at))
    elif sort_by == TargetSortBy.ATTEMPT_COUNT:
        return query.order_by(order_func(InviteTarget.attempt_count))
    else:
        return query.order_by(desc(InviteTarget.created_at))


@router.post("/{task_id}/targets", response_model=InviteTargetResponse)
async def create_target(
    task_id: int,
    target_data: InviteTargetCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Создание нового целевого контакта для задачи"""
    
    # Проверка доступа к задаче
    task = check_task_ownership(task_id, user_id, db)
    
    try:
        # Создание нового контакта
        target = InviteTarget(
            task_id=task_id,
            username=target_data.username,
            phone_number=target_data.phone_number,
            user_id_platform=target_data.user_id_platform,
            email=target_data.email,
            full_name=target_data.full_name,
            bio=target_data.bio,
            profile_photo_url=target_data.profile_photo_url,
            source=target_data.source.value,
            extra_data=target_data.extra_data
        )
        
        db.add(target)
        
        # Обновление счетчика целей в задаче
        task.target_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count() + 1
        task.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(target)
        
        return target
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания контакта: {str(e)}"
        )


@router.post("/{task_id}/targets/bulk", response_model=TargetImportResult)
async def create_targets_bulk(
    task_id: int,
    bulk_data: InviteTargetBulkCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Массовое создание целевых контактов"""
    
    # Проверка доступа к задаче
    task = check_task_ownership(task_id, user_id, db)
    
    start_time = datetime.utcnow()
    created_count = 0
    skipped_count = 0
    error_count = 0
    errors = []
    
    try:
        for i, target_data in enumerate(bulk_data.targets):
            try:
                # Проверка на дубликаты если требуется
                if bulk_data.skip_duplicates:
                    existing = db.query(InviteTarget).filter(
                        InviteTarget.task_id == task_id,
                        or_(
                            and_(InviteTarget.username == target_data.username, target_data.username.isnot(None)),
                            and_(InviteTarget.phone_number == target_data.phone_number, target_data.phone_number.isnot(None)),
                            and_(InviteTarget.user_id_platform == target_data.user_id_platform, target_data.user_id_platform.isnot(None)),
                            and_(InviteTarget.email == target_data.email, target_data.email.isnot(None))
                        )
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue
                
                # Создание нового контакта
                target = InviteTarget(
                    task_id=task_id,
                    username=target_data.username,
                    phone_number=target_data.phone_number,
                    user_id_platform=target_data.user_id_platform,
                    email=target_data.email,
                    full_name=target_data.full_name,
                    bio=target_data.bio,
                    profile_photo_url=target_data.profile_photo_url,
                    source=bulk_data.source.value,
                    extra_data=target_data.extra_data
                )
                
                db.add(target)
                created_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append({
                    "index": i,
                    "error": str(e),
                    "target_data": target_data.dict()
                })
        
        # Обновление счетчика целей в задаче
        task.target_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count() + created_count
        task.updated_at = datetime.utcnow()
        
        db.commit()
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # 🎆 АВТОМАТИЧЕСКИЙ ЗАПУСК ЗАДАЧИ ПОСЛЕ МАССОВОГО ИМПОРТА
        celery_task_id = None
        auto_start_status = None
        
        if created_count > 0 and task.status.value == "PENDING":
            try:
                # Импорт Celery задачи
                from workers.invite_worker import execute_invite_task as celery_execute_task
                
                logger.info(f"🚀 АВТО-СТАРТ: Запуск задачи {task_id} после успешного массового создания {created_count} целей")
                
                # Запуск асинхронной задачи через Celery
                result = celery_execute_task.delay(task_id)
                celery_task_id = result.id
                
                # Обновление статуса задачи
                from app.models.invite_task import TaskStatus
                task.status = TaskStatus.IN_PROGRESS
                task.start_time = datetime.utcnow()
                task.updated_at = datetime.utcnow()
                db.commit()
                
                auto_start_status = "started"
                logger.info(f"✅ АВТО-СТАРТ: Задача {task_id} успешно запущена автоматически после массового создания целей, celery_id={celery_task_id}")
                
            except Exception as auto_start_error:
                logger.error(f"❌ Ошибка автозапуска задачи {task_id} после массового создания целей: {str(auto_start_error)}")
                auto_start_status = f"failed: {str(auto_start_error)}"
                # Не прерываем выполнение, создание целей прошло успешно
        else:
            if created_count == 0:
                auto_start_status = "skipped: no targets created"
            elif task.status.value != "PENDING":
                auto_start_status = f"skipped: task status is {task.status.value}"
        
        result = TargetImportResult(
            total_processed=len(bulk_data.targets),
            created_count=created_count,
            skipped_count=skipped_count,
            error_count=error_count,
            errors=errors,
            duration_seconds=duration
        )
        
        # Добавляем информацию об автозапуске
        result_dict = result.dict()
        result_dict["auto_start"] = {
            "status": auto_start_status,
            "celery_task_id": celery_task_id,
            "task_status": task.status.value,
            "started_at": task.start_time.isoformat() if task.start_time else None
        }
        
        return result_dict
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка массового создания контактов: {str(e)}"
        )


@router.get("/{task_id}/targets", response_model=TargetListResponse)
async def get_targets(
    task_id: int,
    
    # Фильтры
    status: Optional[List[TargetStatus]] = Query(None, description="Фильтр по статусам"),
    source: Optional[List[TargetSource]] = Query(None, description="Фильтр по источникам"),
    has_username: Optional[bool] = Query(None, description="Есть ли username"),
    has_phone: Optional[bool] = Query(None, description="Есть ли телефон"),
    created_after: Optional[datetime] = Query(None, description="Созданы после даты"),
    created_before: Optional[datetime] = Query(None, description="Созданы до даты"),
    search: Optional[str] = Query(None, description="Поиск по полям"),
    
    # Пагинация
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(50, ge=1, le=200, description="Размер страницы"),
    
    # Сортировка
    sort_by: TargetSortBy = Query(TargetSortBy.CREATED_AT, description="Поле для сортировки"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Порядок сортировки"),
    
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Получение списка целевых контактов задачи"""
    
    # Проверка доступа к задаче
    task = check_task_ownership(task_id, user_id, db)
    
    # Создание объекта фильтров
    filters = TargetFilterSchema(
        status=status,
        source=source,
        has_username=has_username,
        has_phone=has_phone,
        created_after=created_after,
        created_before=created_before,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    # Основной запрос
    query = db.query(InviteTarget).filter(InviteTarget.task_id == task_id)
    
    # Применение фильтров
    query = apply_target_filters(query, filters)
    
    # Подсчет общего количества
    total = query.count()
    
    # Применение сортировки
    query = apply_target_sorting(query, sort_by, sort_order)
    
    # Применение пагинации
    offset = (page - 1) * page_size
    targets = query.offset(offset).limit(page_size).all()
    
    # Вычисление метаданных пагинации
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    has_next = page < total_pages
    has_prev = page > 1
    
    # Статистика по статусам
    status_counts = {}
    for status_enum in TargetStatus:
        count = db.query(InviteTarget).filter(
            InviteTarget.task_id == task_id,
            InviteTarget.status == status_enum
        ).count()
        status_counts[status_enum.value] = count
    
    return TargetListResponse(
        items=targets,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
        status_counts=status_counts
    )


@router.get("/{task_id}/targets/{target_id}", response_model=InviteTargetResponse)
async def get_target(
    task_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Получение конкретного целевого контакта"""
    
    # Проверка доступа к задаче
    task = check_task_ownership(task_id, user_id, db)
    
    target = db.query(InviteTarget).filter(
        InviteTarget.id == target_id,
        InviteTarget.task_id == task_id
    ).first()
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Контакт с ID {target_id} не найден в задаче {task_id}"
        )
    
    return target


@router.put("/{task_id}/targets/{target_id}", response_model=InviteTargetResponse)
async def update_target(
    task_id: int,
    target_id: int,
    target_update: InviteTargetUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Обновление целевого контакта"""
    
    # Проверка доступа к задаче
    task = check_task_ownership(task_id, user_id, db)
    
    target = db.query(InviteTarget).filter(
        InviteTarget.id == target_id,
        InviteTarget.task_id == task_id
    ).first()
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Контакт с ID {target_id} не найден в задаче {task_id}"
        )
    
    # Обновление полей
    update_data = target_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(target, field, value)
    
    # Обновление времени изменения
    target.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(target)
        return target
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления контакта: {str(e)}"
        )


@router.delete("/{task_id}/targets/{target_id}")
async def delete_target(
    task_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Удаление целевого контакта"""
    
    # Проверка доступа к задаче
    task = check_task_ownership(task_id, user_id, db)
    
    target = db.query(InviteTarget).filter(
        InviteTarget.id == target_id,
        InviteTarget.task_id == task_id
    ).first()
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Контакт с ID {target_id} не найден в задаче {task_id}"
        )
    
    try:
        db.delete(target)
        
        # Обновление счетчика целей в задаче
        task.target_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count() - 1
        task.updated_at = datetime.utcnow()
        
        db.commit()
        return {"message": f"Контакт {target_id} успешно удален"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления контакта: {str(e)}"
        )


@router.post("/{task_id}/targets/bulk-action", response_model=dict)
async def bulk_target_operations(
    task_id: int,
    bulk_request: TargetBulkRequest,
    db: Session = Depends(get_db)
):
    """Массовые операции с целевыми контактами"""
    user_id = get_current_user_id()
    
    # Проверка доступа к задаче
    task = check_task_ownership(task_id, user_id, db)
    
    # Проверка существования всех контактов
    targets = db.query(InviteTarget).filter(
        InviteTarget.id.in_(bulk_request.target_ids),
        InviteTarget.task_id == task_id
    ).all()
    
    if len(targets) != len(bulk_request.target_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Некоторые контакты не найдены в данной задаче"
        )
    
    try:
        affected_count = 0
        
        if bulk_request.action == TargetBulkAction.DELETE:
            # Удаление контактов
            for target in targets:
                db.delete(target)
                affected_count += 1
                
        elif bulk_request.action == TargetBulkAction.RESET_STATUS:
            # Сброс статуса к pending
            for target in targets:
                target.status = TargetStatus.PENDING
                target.attempt_count = 0
                target.error_message = None
                target.error_code = None
                affected_count += 1
                
        elif bulk_request.action == TargetBulkAction.SET_STATUS:
            # Установка статуса
            new_status = bulk_request.parameters.get("status") if bulk_request.parameters else None
            if not new_status or new_status not in [s.value for s in TargetStatus]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Необходимо указать корректный статус в параметрах"
                )
            
            for target in targets:
                target.status = TargetStatus(new_status)
                affected_count += 1
                
        elif bulk_request.action == TargetBulkAction.RETRY:
            # Повторная попытка для failed контактов
            for target in targets:
                if target.status == TargetStatus.FAILED and target.can_retry:
                    target.status = TargetStatus.PENDING
                    target.error_message = None
                    target.error_code = None
                    affected_count += 1
        
        # Обновление времени изменения для всех затронутых контактов
        for target in targets:
            target.updated_at = datetime.utcnow()
        
        # Обновление счетчика в задаче если были удаления
        if bulk_request.action == TargetBulkAction.DELETE:
            task.target_count = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count() - affected_count
        
        task.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": f"Операция '{bulk_request.action}' выполнена",
            "affected_count": affected_count,
            "total_requested": len(bulk_request.target_ids)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка выполнения массовой операции: {str(e)}"
        )


@router.get("/{task_id}/targets/stats", response_model=TargetStatsResponse)
async def get_target_stats(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Получение статистики по целевым контактам задачи"""
    user_id = get_current_user_id()
    
    # Проверка доступа к задаче
    task = check_task_ownership(task_id, user_id, db)
    
    # Общее количество целей
    total_targets = db.query(InviteTarget).filter(InviteTarget.task_id == task_id).count()
    
    # Статистика по статусам
    status_breakdown = {}
    for status_enum in TargetStatus:
        count = db.query(InviteTarget).filter(
            InviteTarget.task_id == task_id,
            InviteTarget.status == status_enum
        ).count()
        status_breakdown[status_enum.value] = count
    
    # Успешность
    success_count = status_breakdown.get(TargetStatus.INVITED.value, 0) + status_breakdown.get(TargetStatus.ACCEPTED.value, 0)
    success_rate = (success_count / total_targets * 100) if total_targets > 0 else 0
    
    # Среднее количество попыток
    avg_attempts = db.query(func.avg(InviteTarget.attempt_count)).filter(
        InviteTarget.task_id == task_id,
        InviteTarget.attempt_count > 0
    ).scalar() or 0
    
    # Топ ошибок
    top_errors = db.query(
        InviteTarget.error_code,
        func.count(InviteTarget.error_code).label('count')
    ).filter(
        InviteTarget.task_id == task_id,
        InviteTarget.error_code.isnot(None)
    ).group_by(InviteTarget.error_code).order_by(desc('count')).limit(5).all()
    
    top_errors_list = [
        {"error_code": error[0], "count": error[1]}
        for error in top_errors
    ]
    
    return TargetStatsResponse(
        total_targets=total_targets,
        status_breakdown=status_breakdown,
        success_rate=round(success_rate, 2),
        average_attempts=round(float(avg_attempts), 2),
        total_time_spent=None,  # TODO: Будет вычисляться при реализации execution engine
        average_time_per_invite=None,  # TODO: Будет вычисляться при реализации execution engine
        top_errors=top_errors_list
    ) 