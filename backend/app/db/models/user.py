"""User model — registered shopper accounts."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4, UUID

from app.db.base import TimestampedModel


class User(TimestampedModel):
    """A registered shopper account. Wishlist items and preferences
    persist here once a shopper signs up, instead of being scoped only
    to the anonymous device that happened to create them."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    preferred_size: Mapped[str | None] = mapped_column(String(10), nullable=True)
    department: Mapped[str | None] = mapped_column(String(20), nullable=True)
