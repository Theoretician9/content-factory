"""
Parse result model for storing parsed data from all platforms.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, JSON, 
    Boolean, ForeignKey, Enum as SQLEnum, BigInteger
)
from sqlalchemy.orm import relationship

from .base import BaseModel
from ..core.config import Platform


class ParseResult(BaseModel):
    """Universal model for storing parsed data from all platforms."""
    
    __tablename__ = 'parse_results'
    
    # Link to parse task
    task_id = Column(Integer, ForeignKey('parse_tasks.id'), nullable=False, index=True)
    
    # Platform and source info
    platform = Column(SQLEnum(Platform), nullable=False, index=True)
    source_id = Column(String(255), nullable=False, index=True)  # Channel ID, Group ID, etc.
    source_name = Column(String(255), nullable=True)  # Channel name, Group name, etc.
    source_type = Column(String(50), nullable=False)  # 'channel', 'group', 'profile', etc.
    
    # Content identification
    content_id = Column(String(255), nullable=False, index=True)  # Message ID, Post ID, etc.
    content_type = Column(String(50), nullable=False)  # 'message', 'post', 'story', etc.
    
    # Main content
    content_text = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    
    # Author information
    author_id = Column(String(255), nullable=True, index=True)
    author_username = Column(String(255), nullable=True)
    author_name = Column(String(255), nullable=True)
    author_phone = Column(String(20), nullable=True)  # Phone number if accessible
    author_verified = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    content_created_at = Column(DateTime, nullable=True, index=True)
    content_edited_at = Column(DateTime, nullable=True)
    
    # Engagement metrics
    views_count = Column(BigInteger, default=0, nullable=False)
    likes_count = Column(BigInteger, default=0, nullable=False)
    shares_count = Column(BigInteger, default=0, nullable=False)
    comments_count = Column(BigInteger, default=0, nullable=False)
    reactions_count = Column(BigInteger, default=0, nullable=False)
    
    # Media information
    has_media = Column(Boolean, default=False, nullable=False)
    media_count = Column(Integer, default=0, nullable=False)
    media_types = Column(JSON, nullable=True)  # ['photo', 'video', 'document']
    
    # Geographic data
    location_name = Column(String(255), nullable=True)
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    
    # Language and content analysis
    language = Column(String(10), nullable=True)
    sentiment_score = Column(String(20), nullable=True)  # 'positive', 'negative', 'neutral'
    
    # Platform-specific data
    platform_data = Column(JSON, nullable=True)  # Store platform-specific fields
    """
    Example platform_data for Telegram:
    {
        "message_id": 12345,
        "chat_id": -1001234567890,
        "forward_from": "channel_name",
        "reply_to_message_id": 12344,
        "sticker_set": "AnimatedEmojies",
        "poll_data": {...},
        "contact_data": {...}
    }
    
    Example platform_data for Instagram:
    {
        "post_id": "ABC123",
        "product_tags": [...],
        "hashtags": ["#fashion", "#style"],
        "mentions": ["@brand"],
        "story_highlights": true
    }
    """
    
    # Links and references
    urls = Column(JSON, nullable=True)  # List of URLs found in content
    mentions = Column(JSON, nullable=True)  # List of @mentions
    hashtags = Column(JSON, nullable=True)  # List of #hashtags
    
    # Content flags
    is_forwarded = Column(Boolean, default=False, nullable=False)
    is_reply = Column(Boolean, default=False, nullable=False)
    is_edited = Column(Boolean, default=False, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    
    # Raw data backup
    raw_data = Column(JSON, nullable=True)  # Complete raw response from platform API
    
    # Indexing and search
    search_vector = Column(Text, nullable=True)  # For full-text search
    
    def __repr__(self):
        return f"<ParseResult(id={self.id}, platform={self.platform.value}, content_id={self.content_id})>"
    
    @property
    def has_engagement(self) -> bool:
        """Check if content has any engagement metrics."""
        return any([
            self.views_count > 0,
            self.likes_count > 0,
            self.shares_count > 0,
            self.comments_count > 0,
            self.reactions_count > 0
        ])
    
    def get_engagement_total(self) -> int:
        """Get total engagement count."""
        return (
            self.likes_count + 
            self.shares_count + 
            self.comments_count + 
            self.reactions_count
        )
    
    def extract_keywords(self) -> list:
        """Extract keywords from content for search."""
        if not self.content_text:
            return []
        
        # Simple keyword extraction (can be enhanced with NLP)
        import re
        words = re.findall(r'\b\w+\b', self.content_text.lower())
        return list(set(word for word in words if len(word) > 3))


class ParseResultMedia(BaseModel):
    """Model for storing media files associated with parse results."""
    
    __tablename__ = 'parse_result_media'
    
    # Link to parse result
    result_id = Column(Integer, ForeignKey('parse_results.id'), nullable=False, index=True)
    
    # Media information
    media_type = Column(String(20), nullable=False)  # 'photo', 'video', 'audio', 'document'
    media_url = Column(String(1000), nullable=True)  # Original URL
    local_path = Column(String(500), nullable=True)  # Local file path if downloaded
    
    # Media metadata
    file_name = Column(String(255), nullable=True)
    file_size = Column(BigInteger, nullable=True)  # Size in bytes
    mime_type = Column(String(100), nullable=True)
    
    # Media dimensions (for images/videos)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds for video/audio
    
    # Download status
    is_downloaded = Column(Boolean, default=False, nullable=False)
    download_error = Column(Text, nullable=True)
    
    # Platform-specific media data
    platform_media_data = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<ParseResultMedia(id={self.id}, media_type={self.media_type}, file_name={self.file_name})>" 