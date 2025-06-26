"""
Account state management for Telegram accounts used in parsing.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from enum import Enum as PyEnum

from .base import Base


class AccountStatus(PyEnum):
    """Account status enumeration."""
    FREE = "free"           # Account is available for new tasks
    BUSY = "busy"           # Account is currently parsing
    BLOCKED = "blocked"     # Account is blocked due to FloodWait
    BANNED = "banned"       # Account is banned/suspended
    ERROR = "error"         # Account has errors


class AccountState(Base):
    """
    Track the state of Telegram accounts used for parsing.
    
    This model ensures proper account-level task distribution and FloodWait handling.
    """
    __tablename__ = "account_states"

    id = Column(Integer, primary_key=True, index=True)
    
    # Account identification
    account_id = Column(String(100), unique=True, nullable=False, index=True)  # From integration-service
    session_id = Column(String(100), nullable=True)  # Telegram session identifier
    
    # Current status
    status = Column(String(20), default=AccountStatus.FREE.value, nullable=False, index=True)
    
    # Task assignment
    current_task_id = Column(String(100), nullable=True, index=True)  # Currently assigned task
    
    # Blocking/timing information
    blocked_until = Column(DateTime, nullable=True)  # When FloodWait expires
    last_activity = Column(DateTime, default=func.now(), nullable=False)  # Last time account was used
    last_flood_wait = Column(DateTime, nullable=True)  # Last FloodWait occurrence
    
    # Account metadata
    account_info = Column(Text, nullable=True)  # JSON string with account details
    error_message = Column(Text, nullable=True)  # Last error message
    total_tasks_completed = Column(Integer, default=0)  # Statistics
    total_flood_waits = Column(Integer, default=0)  # FloodWait count
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<AccountState(account_id='{self.account_id}', status='{self.status}', current_task='{self.current_task_id}')>"

    def is_available(self) -> bool:
        """Check if account is available for new tasks."""
        if self.status != AccountStatus.FREE.value:
            return False
        
        # Check if FloodWait has expired
        if self.blocked_until and datetime.utcnow() < self.blocked_until:
            return False
            
        return True

    def is_blocked(self) -> bool:
        """Check if account is currently blocked by FloodWait."""
        if self.blocked_until and datetime.utcnow() < self.blocked_until:
            return True
        return False

    def time_until_unblocked(self) -> int:
        """Get seconds until account is unblocked, 0 if not blocked."""
        if not self.blocked_until:
            return 0
        
        remaining = self.blocked_until - datetime.utcnow()
        return max(0, int(remaining.total_seconds()))

    def assign_task(self, task_id: str):
        """Assign a task to this account."""
        self.current_task_id = task_id
        self.status = AccountStatus.BUSY.value
        self.last_activity = datetime.utcnow()

    def complete_task(self):
        """Mark task as completed and free the account."""
        self.current_task_id = None
        self.status = AccountStatus.FREE.value
        self.last_activity = datetime.utcnow()
        self.total_tasks_completed += 1

    def block_for_flood_wait(self, seconds: int, error_message: str = None):
        """Block account due to FloodWait."""
        self.status = AccountStatus.BLOCKED.value
        self.blocked_until = datetime.utcnow() + timedelta(seconds=seconds)
        self.last_flood_wait = datetime.utcnow()
        self.total_flood_waits += 1
        if error_message:
            self.error_message = error_message

    def mark_error(self, error_message: str):
        """Mark account as having an error."""
        self.status = AccountStatus.ERROR.value
        self.error_message = error_message
        self.current_task_id = None  # Free the task if assigned

    def reset_to_free(self):
        """Reset account to free status (manual recovery)."""
        self.status = AccountStatus.FREE.value
        self.current_task_id = None
        self.blocked_until = None
        self.error_message = None 