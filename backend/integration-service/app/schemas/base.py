from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from datetime import datetime
from uuid import UUID

class BaseResponse(BaseModel):
    """Базовая схема ответа"""
    success: bool = True
    message: str = "OK"
    
class ErrorResponse(BaseResponse):
    """Схема ответа об ошибке"""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class BaseModelResponse(BaseModel):
    """Базовая схема для моделей с общими полями"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            UUID: lambda uuid: str(uuid)
        }

class PaginationParams(BaseModel):
    """Схема для параметров пагинации"""
    page: int = Field(default=1, ge=1, description="Номер страницы")
    size: int = Field(default=20, ge=1, le=100, description="Размер страницы")
    
class PaginatedResponse(BaseModel):
    """Схема для пагинированных ответов"""
    items: list
    total: int
    page: int
    size: int
    pages: int
    
    @classmethod
    def create(cls, items: list, total: int, page: int, size: int):
        pages = (total + size - 1) // size
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        ) 