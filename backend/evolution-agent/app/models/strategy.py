from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import BaseModel, Base


class Strategy(Base, BaseModel):
    """
    Стратегия ведения канала (см. ТЗ, раздел 6.1 `strategies`).
    Для (user_id, channel_id) активна не более одной стратегии одновременно.
    """

    __tablename__ = "strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(Integer, nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True)

    version = Column(Integer, nullable=False, default=1)

    persona_json = Column(JSONB, nullable=False)
    content_mix_json = Column(JSONB, nullable=False)
    schedule_rules_json = Column(JSONB, nullable=False)

    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "channel_id",
            "is_active",
            name="uq_strategies_user_channel_active",
        ),
    )

