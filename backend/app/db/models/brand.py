"""Brand registry model — Phase 1."""

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4, UUID

from app.db.base import TimestampedModel


class Brand(TimestampedModel):
    """Brand registry — one per Tier-1 Shopify store."""

    __tablename__ = "brand_registry"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
