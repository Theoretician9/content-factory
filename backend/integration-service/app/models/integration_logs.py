from sqlalchemy import Column, Integer, String, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from .base import BaseModel

class IntegrationLog(BaseModel):
    """Модель для хранения логов интеграций"""
    __tablename__ = "integration_logs"
    
    user_id = Column(Integer, nullable=False, index=True)
    integration_type = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    details = Column(JSONB, default={})
    error_message = Column(Text, nullable=True)
    
    __table_args__ = (
        CheckConstraint(
            status.in_(['success', 'error', 'pending']),
            name='valid_log_status'
        ),
    )
    
    def __repr__(self):
        return f"<IntegrationLog(id={self.id}, user_id={self.user_id}, type={self.integration_type}, action={self.action}, status={self.status})>" 