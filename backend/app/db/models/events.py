"""Session events (analytics) model — Phase 1."""

from sqlalchemy import String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID
from datetime import datetime, timezone

from app.db.base import Base


class SessionEvent(Base):
    """Analytics event — north-star metric: turns-to-click."""

    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.device_id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # turn_fast_path, turn_llm, product_click, etc.
    product_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
