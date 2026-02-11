from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum as SQLEnum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel, Base


class AgentTaskStatus(str):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTask(Base, BaseModel):
    """
    Задачи оркестратора evolution-agent (см. ТЗ, раздел 6.5 `agent_tasks`).
    Опциональный, но полезный трекер для отладки и анализа.
    """

    __tablename__ = "agent_tasks"

    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(Integer, nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True)

    slot_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    status = Column(
        SQLEnum(
            AgentTaskStatus.CREATED,
            AgentTaskStatus.RUNNING,
            AgentTaskStatus.COMPLETED,
            AgentTaskStatus.FAILED,
            name="agent_task_status",
        ),
        nullable=False,
        default=AgentTaskStatus.CREATED,
        index=True,
    )

    goal = Column(String(255), nullable=False)
    user_request = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

