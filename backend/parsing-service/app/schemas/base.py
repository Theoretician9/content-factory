"""
Base Pydantic schemas for multi-platform parsing service.
"""

from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field, ConfigDict

from ..core.config import Platform, TaskStatus, TaskPriority


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


class HealthResponse(BaseSchema):
    """Health check response schema."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")
    platform_support: List[Platform] = Field(..., description="Supported platforms")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = Field(None, description="Additional health details")


class ErrorResponse(BaseSchema):
    """Error response schema."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationParams(BaseSchema):
    """Pagination parameters schema."""
    
    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.size


class PaginatedResponse(BaseSchema):
    """Paginated response schema."""
    
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    
    @classmethod
    def create(cls, items: List[Any], total: int, page: int, size: int):
        """Create paginated response."""
        pages = (total + size - 1) // size  # Ceiling division
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        ) 