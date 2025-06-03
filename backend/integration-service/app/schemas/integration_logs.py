from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from .base import BaseModelResponse

class IntegrationLogResponse(BaseModelResponse):
    """Схема ответа с данными лога интеграции"""
    user_id: int
    integration_type: str
    action: str
    status: str
    details: Dict[str, Any]
    error_message: Optional[str] = None
    
class IntegrationLogCreate(BaseModel):
    """Схема создания лога интеграции"""
    user_id: int
    integration_type: str = Field(..., description="Тип интеграции (telegram, vk, etc)")
    action: str = Field(..., description="Выполненное действие")
    status: str = Field(..., description="Статус: success, error, pending")
    details: Optional[Dict[str, Any]] = {}
    error_message: Optional[str] = None 