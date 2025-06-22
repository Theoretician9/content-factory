"""
Parse task model for multi-platform parsing service.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, JSON, 
    Boolean, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from .base import BaseModel
from ..core.config import Platform, TaskStatus, TaskPriority


class ParseTask(BaseModel):
    """Universal parse task model for all platforms."""
    
    __tablename__ = 'parse_tasks'
    
    # Task identification
    task_id = Column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # User and authentication
    user_id = Column(Integer, nullable=False, index=True)
    
    # Platform-specific
    platform = Column(SQLEnum(Platform), nullable=False, index=True)
    
    # Task metadata
    task_type = Column(String(50), nullable=False)  # 'parse_group', 'search_communities', etc.
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Task configuration
    config = Column(JSON, nullable=False)  # Platform-specific configuration
    """
    Example config structure:
    For Telegram:
    {
        "targets": ["@channel1", "@group2"],
        "message_limit": 10000,
        "include_media": true,
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "filters": {
            "keywords": ["bitcoin", "crypto"],
            "exclude_keywords": ["spam"]
        }
    }
    
    For Instagram (planned):
    {
        "targets": ["@username1", "#hashtag1"],
        "post_limit": 1000,
        "include_stories": false,
        "media_types": ["photo", "video"]
    }
    """
    
    # Task status and priority
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    priority = Column(SQLEnum(TaskPriority), default=TaskPriority.NORMAL, nullable=False, index=True)
    
    # Progress tracking
    progress = Column(Integer, default=0, nullable=False)  # 0-100 percentage
    total_items = Column(Integer, default=0, nullable=False)
    processed_items = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    
    # Rate limiting and account management  
    account_ids = Column(JSON, nullable=True)  # List of account IDs to use
    current_account_id = Column(String(100), nullable=True)  # Currently active account
    
    # Resume functionality
    resume_data = Column(JSON, nullable=True)  # Data needed to resume parsing
    """
    Example resume_data:
    {
        "last_message_id": 12345,
        "last_offset": 1000,
        "processed_targets": ["@channel1"],
        "current_target": "@group2",
        "checkpoint_data": {...}
    }
    """
    
    # Output configuration
    output_format = Column(String(20), default='json', nullable=False)  # json, csv, xlsx
    include_metadata = Column(Boolean, default=True, nullable=False)
    
    # Results reference
    result_file_path = Column(String(500), nullable=True)  # Path to result file
    result_count = Column(Integer, default=0, nullable=False)
    
    # Celery task ID for cancellation
    celery_task_id = Column(String(100), nullable=True, index=True)
    
    def __repr__(self):
        return f"<ParseTask(id={self.id}, task_id={self.task_id}, platform={self.platform.value}, status={self.status.value})>"
    
    @property
    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status == TaskStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if task failed."""
        return self.status == TaskStatus.FAILED
    
    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.is_failed
    
    def update_progress(self, processed: int, total: int = None):
        """Update task progress."""
        self.processed_items = processed
        if total is not None:
            self.total_items = total
        
        if self.total_items > 0:
            self.progress = min(100, int((self.processed_items / self.total_items) * 100))
        else:
            self.progress = 0 