"""
Parse task schemas for API validation and serialization.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field, validator

from .base import BaseSchema
from ..core.config import Platform, TaskStatus, TaskPriority


class ParseTaskConfig(BaseSchema):
    """Base configuration for parse tasks."""
    
    targets: List[str] = Field(..., description="List of targets to parse (channels, groups, etc.)")
    message_limit: Optional[int] = Field(10000, ge=1, le=100000, description="Maximum messages to parse")
    include_media: bool = Field(True, description="Include media files in parsing")
    date_from: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    
    @validator('date_from', 'date_to')
    def validate_date_format(cls, v):
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v


class TelegramParseConfig(ParseTaskConfig):
    """Telegram-specific parse configuration."""
    
    filters: Optional[Dict[str, Any]] = Field(None, description="Message filters")
    download_media: bool = Field(False, description="Download media files locally")
    include_deleted: bool = Field(False, description="Include information about deleted messages")
    
    class Config:
        schema_extra = {
            "example": {
                "targets": ["@cryptonews", "@bitcoinchannel"],
                "message_limit": 5000,
                "include_media": True,
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
                "filters": {
                    "keywords": ["bitcoin", "crypto"],
                    "exclude_keywords": ["spam", "promotion"],
                    "min_length": 10
                },
                "download_media": False,
                "include_deleted": False
            }
        }


class CreateParseTaskRequest(BaseSchema):
    """Request schema for creating parse tasks."""
    
    platform: Platform = Field(..., description="Platform to parse")
    task_type: str = Field(..., description="Type of parsing task")
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    config: Dict[str, Any] = Field(..., description="Platform-specific configuration")
    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Task priority")
    output_format: str = Field("json", description="Output format")


class ParseTaskResponse(BaseSchema):
    """Response schema for parse tasks."""
    
    id: int
    task_id: str
    user_id: int
    platform: Platform
    task_type: str
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    progress: int
    total_items: int
    processed_items: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    result_count: int


class UpdateParseTaskRequest(BaseSchema):
    """Request schema for updating parse tasks."""
    
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None


class ParseTaskListParams(BaseSchema):
    """Parameters for listing parse tasks."""
    
    platform: Optional[Platform] = Field(None, description="Filter by platform")
    status: Optional[TaskStatus] = Field(None, description="Filter by status")
    task_type: Optional[str] = Field(None, description="Filter by task type")
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: str = Field("created_at", description="Sort field")
    sort_order: str = Field("desc", description="Sort order (asc/desc)")
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        allowed_fields = ['created_at', 'updated_at', 'priority', 'status', 'progress']
        if v not in allowed_fields:
            raise ValueError(f'Sort field must be one of: {", ".join(allowed_fields)}')
        return v
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v.lower() not in ['asc', 'desc']:
            raise ValueError('Sort order must be "asc" or "desc"')
        return v.lower()


class TaskStatsResponse(BaseSchema):
    """Response schema for task statistics."""
    
    total_tasks: int = Field(..., description="Total number of tasks")
    by_status: Dict[str, int] = Field(..., description="Task count by status")
    by_platform: Dict[str, int] = Field(..., description="Task count by platform")
    by_priority: Dict[str, int] = Field(..., description="Task count by priority")
    total_results: int = Field(..., description="Total number of parsed results")
    active_tasks: int = Field(..., description="Number of currently running tasks") 