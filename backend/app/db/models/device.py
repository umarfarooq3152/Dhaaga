"""Device model — Phase 1."""

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4, UUID
from datetime import datetime, timezone

from app.db.base import TimestampedModel


class Device(TimestampedModel):
    """Anonymous device session tracking."""

    __tablename__ = "devices"

    device_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    size: Mapped[str | None] = mapped_column(nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
