from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from uuid import UUID
import logging

from ..models.base import Base

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)

class BaseCRUDService(Generic[ModelType]):
    """Базовый CRUD сервис для работы с моделями"""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    async def create(
        self, 
        session: AsyncSession, 
        obj_data: Dict[str, Any]
    ) -> ModelType:
        """Создание нового объекта"""
        try:
            obj = self.model(**obj_data)
            session.add(obj)
            await session.flush()
            await session.refresh(obj)
            logger.info(f"Created {self.model.__name__} with id: {obj.id}")
            return obj
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            raise
    
    async def get_by_id(
        self, 
        session: AsyncSession, 
        obj_id: UUID
    ) -> Optional[ModelType]:
        """Получение объекта по ID"""
        try:
            result = await session.execute(
                select(self.model).where(self.model.id == obj_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} by id {obj_id}: {e}")
            raise
    
    async def get_multi(
        self,
        session: AsyncSession,
        filters: Optional[Dict[str, Any]] = None,
        offset: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """Получение списка объектов с фильтрацией"""
        try:
            query = select(self.model)
            
            # Детальное логирование фильтров
            logger.info(f"🔍 get_multi for {self.model.__name__}: filters={filters}")
            
            # Применяем фильтры
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        logger.info(f"🔍 Applying filter: {field} == {value}")
                        query = query.where(getattr(self.model, field) == value)
                    else:
                        logger.warning(f"⚠️ Field {field} does not exist in {self.model.__name__}")
            
            # Сортировка
            if order_by and hasattr(self.model, order_by):
                query = query.order_by(getattr(self.model, order_by))
            else:
                query = query.order_by(self.model.created_at.desc())
            
            # Пагинация
            query = query.offset(offset).limit(limit)
            
            # Логируем итоговый запрос
            logger.info(f"🔍 Executing query for {self.model.__name__}")
            
            result = await session.execute(query)
            items = result.scalars().all()
            
            # Детальное логирование результатов
            logger.info(f"📊 get_multi result for {self.model.__name__}: found {len(items)} items")
            for item in items:
                if hasattr(item, 'user_id'):
                    logger.info(f"  📱 Item {item.id}: user_id={item.user_id}")
                else:
                    logger.info(f"  📱 Item {item.id}: no user_id field")
            
            return items
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} list: {e}")
            raise
    
    async def update(
        self,
        session: AsyncSession,
        obj_id: UUID,
        obj_data: Dict[str, Any]
    ) -> Optional[ModelType]:
        """Обновление объекта"""
        try:
            # Удаляем None значения
            obj_data = {k: v for k, v in obj_data.items() if v is not None}
            
            await session.execute(
                update(self.model)
                .where(self.model.id == obj_id)
                .values(**obj_data)
            )
            
            # Получаем обновленный объект
            result = await session.execute(
                select(self.model).where(self.model.id == obj_id)
            )
            obj = result.scalar_one_or_none()
            
            if obj:
                logger.info(f"Updated {self.model.__name__} with id: {obj_id}")
            
            return obj
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__} {obj_id}: {e}")
            raise 