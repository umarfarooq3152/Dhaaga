"""Wishlist item model — Phase 1."""

from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID
from datetime import datetime, timezone

from app.db.base import Base


class WishlistItem(Base):
    """Wishlist entry — device_id + composite product_id."""

    __tablename__ = "wishlist_items"

    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
