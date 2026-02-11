from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID, BigInteger
from sqlalchemy.orm import relationship

from .base import BaseModel, Base
from .calendar import CalendarSlot


class Post(Base, BaseModel):
    """
    Сгенерированный пост (см. ТЗ, раздел 6.3 `posts`).
    Один пост привязан к одному слоту.
    """

    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(Integer, nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True)

    slot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("calendar_slots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    content_text = Column(Text, nullable=False)
    hashtags = Column(JSONB, nullable=True)
    cta = Column(Text, nullable=True)

    meta_stats = Column(JSONB, nullable=True)

    telegram_message_id = Column(BigInteger, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    slot = relationship(CalendarSlot, backref="post")

