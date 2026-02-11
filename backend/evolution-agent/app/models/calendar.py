from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel, Base
from .strategy import Strategy


class CalendarSlotStatus(str):
    PLANNED = "planned"
    PROCESSING = "processing"
    READY = "ready"
    PUBLISHED = "published"
    FAILED = "failed"


class CalendarSlot(Base, BaseModel):
    """
    Слот контент‑плана (см. ТЗ, раздел 6.2 `calendar_slots`).
    """

    __tablename__ = "calendar_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(Integer, nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True)

    strategy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
    )

    dt = Column(DateTime, nullable=False, index=True)

    status = Column(
        SQLEnum(
            CalendarSlotStatus.PLANNED,
            CalendarSlotStatus.PROCESSING,
            CalendarSlotStatus.READY,
            CalendarSlotStatus.PUBLISHED,
            CalendarSlotStatus.FAILED,
            name="calendar_slot_status",
        ),
        nullable=False,
        default=CalendarSlotStatus.PLANNED,
        index=True,
    )

    pillar = Column(Text, nullable=True)
    locked_by = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    strategy = relationship(Strategy, backref="calendar_slots")

