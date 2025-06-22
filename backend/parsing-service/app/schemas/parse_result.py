"""
Parse result schemas for API validation and serialization.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field

from .base import BaseSchema
from ..core.config import Platform


class ParseResultResponse(BaseSchema):
    """Response schema for parse results."""
    
    id: int
    task_id: int
    platform: Platform
    source_id: str
    source_name: Optional[str]
    source_type: str
    content_id: str
    content_type: str
    content_text: Optional[str]
    author_id: Optional[str]
    author_username: Optional[str]
    author_name: Optional[str]
    content_created_at: Optional[datetime]
    views_count: int
    likes_count: int
    shares_count: int
    comments_count: int
    has_media: bool
    media_count: int
    language: Optional[str]
    urls: Optional[List[str]]
    mentions: Optional[List[str]]
    hashtags: Optional[List[str]]
    is_forwarded: bool
    is_reply: bool
    created_at: datetime


class ParseResultListParams(BaseSchema):
    """Parameters for listing parse results."""
    
    task_id: Optional[int] = None
    platform: Optional[Platform] = None
    source_id: Optional[str] = None
    content_type: Optional[str] = None
    author_username: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    has_media: Optional[bool] = None
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)
    sort_by: str = Field("created_at")
    sort_order: str = Field("desc")


class ParseResultStatsResponse(BaseSchema):
    """Response schema for parse result statistics."""
    
    total_results: int
    by_platform: Dict[str, int]
    by_source_type: Dict[str, int] 
    by_content_type: Dict[str, int]
    total_media: int
    date_range: Dict[str, Optional[str]]
    top_sources: List[Dict[str, Any]]
    engagement_stats: Dict[str, int] 