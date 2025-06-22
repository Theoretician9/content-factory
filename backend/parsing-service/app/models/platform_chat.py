"""
Platform chat/community model for storing information about channels, groups, etc.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, JSON, 
    Boolean, Enum as SQLEnum, BigInteger
)

from .base import BaseModel
from ..core.config import Platform


class PlatformChat(BaseModel):
    """Universal model for storing information about chats/communities across platforms."""
    
    __tablename__ = 'platform_chats'
    
    # Platform and identification
    platform = Column(SQLEnum(Platform), nullable=False, index=True)
    chat_id = Column(String(255), nullable=False, index=True)
    username = Column(String(255), nullable=True, index=True)
    
    # Basic information
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    chat_type = Column(String(50), nullable=False)  # 'channel', 'group', 'supergroup'
    
    # Status flags
    is_verified = Column(Boolean, default=False, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)
    
    # Statistics
    members_count = Column(BigInteger, default=0, nullable=False)
    messages_count = Column(BigInteger, default=0, nullable=False)
    
    # Platform-specific data
    platform_data = Column(JSON, nullable=True)
    
    # Discovery
    keywords = Column(JSON, nullable=True)
    last_parsed = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<PlatformChat(platform={self.platform.value}, chat_id={self.chat_id})>"
    
    @property
    def display_name(self) -> str:
        """Get display name for the chat."""
        if self.title:
            return self.title
        elif self.username:
            return f"@{self.username}"
        else:
            return f"{self.platform.value}_{self.chat_id}"
    
    @property
    def full_username(self) -> str:
        """Get full username with @ prefix."""
        if self.username:
            return f"@{self.username}" if not self.username.startswith('@') else self.username
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if chat is considered active based on recent activity."""
        if not self.last_parsed:
            return False
        
        from datetime import datetime, timedelta
        threshold = datetime.utcnow() - timedelta(days=30)  # Active if had messages in last 30 days
        return self.last_parsed >= threshold
    
    @property
    def engagement_rate(self) -> float:
        """Calculate rough engagement rate based on available data."""
        if self.members_count <= 0:
            return 0.0
        
        # Simple approximation - can be enhanced with more sophisticated metrics
        active_members = self.members_count
        return (active_members / self.members_count) * 100 if self.members_count > 0 else 0.0
    
    def update_statistics(self, members: int = None, messages: int = None):
        """Update chat statistics."""
        if members is not None:
            self.members_count = members
        if messages is not None:
            self.messages_count = messages
        
        self.last_updated = datetime.utcnow()
    
    def add_keywords(self, new_keywords: list):
        """Add keywords for search and discovery."""
        if self.keywords is None:
            self.keywords = []
        
        # Add new keywords, avoiding duplicates
        for keyword in new_keywords:
            if keyword.lower() not in [k.lower() for k in self.keywords]:
                self.keywords.append(keyword.lower())
    
    def calculate_data_completeness(self) -> int:
        """Calculate data completeness percentage."""
        total_fields = 0
        filled_fields = 0
        
        # Basic required fields
        fields_to_check = [
            'title', 'description', 'chat_type', 'members_count',
            'is_verified', 'is_private', 'language_code'
        ]
        
        for field in fields_to_check:
            total_fields += 1
            value = getattr(self, field)
            if value is not None and value != '' and value != 0:
                filled_fields += 1
        
        # Optional but valuable fields
        optional_fields = ['about', 'category', 'photo_url', 'website_url', 'location']
        for field in optional_fields:
            total_fields += 1
            value = getattr(self, field)
            if value is not None and value != '':
                filled_fields += 1
        
        completeness = int((filled_fields / total_fields) * 100) if total_fields > 0 else 0
        self.data_completeness = completeness
        return completeness 