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