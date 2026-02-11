from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import BaseModel, Base
from .post import Post


class MemoryLog(Base, BaseModel):
    """
    Логи обратной связи по постам (см. ТЗ, раздел 6.4 `memory_logs`).
    """

    __tablename__ = "memory_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(Integer, nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True)

    post_id = Column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    metrics_snapshot = Column(JSONB, nullable=False)

    collected_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    post = relationship(Post, backref="memory_logs")

