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
    title: str = Field(..., min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    config: Dict[str, Any] = Field(..., description="Platform-specific configuration")
    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Task priority")
    scheduled_at: Optional[datetime] = Field(None, description="Schedule task for later execution")
    output_format: str = Field("json", description="Output format (json, csv, xlsx)")
    include_metadata: bool = Field(True, description="Include metadata in results")
    
    @validator('task_type')
    def validate_task_type(cls, v):
        allowed_types = ['parse_group', 'parse_channel', 'search_communities', 'export_members']
        if v not in allowed_types:
            raise ValueError(f'Task type must be one of: {", ".join(allowed_types)}')
        return v
    
    @validator('output_format')
    def validate_output_format(cls, v):
        allowed_formats = ['json', 'csv', 'xlsx']
        if v not in allowed_formats:
            raise ValueError(f'Output format must be one of: {", ".join(allowed_formats)}')
        return v


class ParseTaskResponse(BaseSchema):
    """Response schema for parse tasks."""
    
    id: int = Field(..., description="Task database ID")
    task_id: str = Field(..., description="Unique task identifier")
    user_id: int = Field(..., description="User ID who created the task")
    platform: Platform = Field(..., description="Platform being parsed")
    task_type: str = Field(..., description="Type of parsing task")
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    config: Dict[str, Any] = Field(..., description="Task configuration")
    status: TaskStatus = Field(..., description="Current task status")
    priority: TaskPriority = Field(..., description="Task priority")
    progress: int = Field(..., description="Completion progress (0-100)")
    total_items: int = Field(..., description="Total items to process")
    processed_items: int = Field(..., description="Items processed so far")
    created_at: datetime = Field(..., description="Task creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Task start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    result_count: int = Field(..., description="Number of results found")
    output_format: str = Field(..., description="Output format")


class UpdateParseTaskRequest(BaseSchema):
    """Request schema for updating parse tasks."""
    
    status: Optional[TaskStatus] = Field(None, description="New task status")
    priority: Optional[TaskPriority] = Field(None, description="New task priority")
    scheduled_at: Optional[datetime] = Field(None, description="Reschedule task")


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