from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
import logging

from .base import BaseCRUDService
from ..models.integration_logs import IntegrationLog
from ..schemas.integration_logs import IntegrationLogCreate

logger = logging.getLogger(__name__)

class IntegrationLogService(BaseCRUDService[IntegrationLog]):
    """Сервис для работы с логами интеграций"""
    
    def __init__(self):
        super().__init__(IntegrationLog)
    
    async def log_action(
        self,
        session: AsyncSession,
        user_id: int,
        integration_type: str,
        action: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> IntegrationLog:
        """Создание записи в логе"""
        log_data = {
            "user_id": user_id,
            "integration_type": integration_type,
            "action": action,
            "status": status,
            "details": details or {},
            "error_message": error_message
        }
        
        return await self.create(session, log_data)
    
    async def log_integration_action(
        self,
        session: AsyncSession,
        user_id: int,
        integration_type: str,
        action: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> IntegrationLog:
        """Alias for log_action for Account Manager compatibility"""
        return await self.log_action(
            session=session,
            user_id=user_id,
            integration_type=integration_type,
            action=action,
            status=status,
            details=details,
            error_message=error_message
        )
    
    async def get_user_logs(
        self,
        session: AsyncSession,
        user_id: int,
        integration_type: Optional[str] = None,
        status: Optional[str] = None,
        days_back: int = 30,
        offset: int = 0,
        limit: int = 100
    ) -> List[IntegrationLog]:
        """Получение логов пользователя"""
        filters = {"user_id": user_id}
        
        if integration_type:
            filters["integration_type"] = integration_type
        
        if status:
            filters["status"] = status
        
        # Фильтр по дате (последние N дней)
        date_from = datetime.utcnow() - timedelta(days=days_back)
        
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.created_at >= date_from
        )
        
        if integration_type:
            query = query.where(self.model.integration_type == integration_type)
        
        if status:
            query = query.where(self.model.status == status)
        
        query = query.order_by(desc(self.model.created_at)).offset(offset).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_error_stats(
        self,
        session: AsyncSession,
        user_id: Optional[int] = None,
        integration_type: Optional[str] = None,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """Получение статистики ошибок"""
        date_from = datetime.utcnow() - timedelta(days=days_back)
        
        # Базовый запрос
        base_query = select(self.model).where(
            self.model.created_at >= date_from
        )
        
        if user_id:
            base_query = base_query.where(self.model.user_id == user_id)
        
        if integration_type:
            base_query = base_query.where(self.model.integration_type == integration_type)
        
        # Общее количество записей
        total_query = select(func.count(self.model.id)).select_from(base_query.subquery())
        total_result = await session.execute(total_query)
        total_count = total_result.scalar()
        
        # Количество ошибок
        error_query = base_query.where(self.model.status == 'error')
        error_count_query = select(func.count(self.model.id)).select_from(error_query.subquery())
        error_result = await session.execute(error_count_query)
        error_count = error_result.scalar()
        
        # Процент ошибок
        error_rate = (error_count / total_count * 100) if total_count > 0 else 0
        
        return {
            "total_actions": total_count,
            "error_count": error_count,
            "success_count": total_count - error_count,
            "error_rate": round(error_rate, 2),
            "period_days": days_back
        } 