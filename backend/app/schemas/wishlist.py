"""Wishlist schema."""

from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.schemas.product import Product


class WishlistItemResponse(BaseModel):
    """Wishlist item with hydrated product."""

    product: Product
    added_at: datetime


class WishlistResponse(BaseModel):
    """User's complete wishlist."""

    device_id: UUID
    items: list[WishlistItemResponse]
    total: int
