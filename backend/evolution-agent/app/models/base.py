from datetime import datetime

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import declarative_mixin, declared_attr
from sqlalchemy.orm import declarative_base


Base = declarative_base()


@declarative_mixin
class BaseModel:
    """Базовая модель с id/created_at/updated_at, как в других сервисах."""

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    @declared_attr
    def __tablename__(cls) -> str:  # type: ignore[override]
        return cls.__name__.lower()

