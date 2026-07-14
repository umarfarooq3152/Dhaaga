"""Collection schema."""

from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from app.schemas.product import Product


class CollectionResponse(BaseModel):
    """Collection metadata (tile on home screen)."""

    id: UUID
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class CollectionProductsResponse(BaseModel):
    """Collection with resolved products (live from cache)."""

    id: str  # Collection ID
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    items: list[Product]  # Products matching filter
    total: int  # Total matching products
    page: int
    page_size: int
    has_more: bool

