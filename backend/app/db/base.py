"""SQLAlchemy declarative base and shared utilities."""

from datetime import datetime, timezone
from sqlalchemy import DateTime, func
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from typing import Optional

Base = declarative_base()


class TimestampedModel(Base):
    """Base model with automatic timestamps."""

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
