"""Wishlist repository — data access for wishlist items."""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.wishlist import WishlistItem


class WishlistRepository:
    """Repository for wishlist_items table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, device_id: UUID) -> list[WishlistItem]:
        """Get all wishlist items for a device."""
        result = await self.session.execute(
            select(WishlistItem)
            .where(WishlistItem.device_id == device_id)
            .order_by(WishlistItem.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_product_id(self, device_id: UUID, product_id: str) -> Optional[WishlistItem]:
        """Get wishlist item by product ID."""
        result = await self.session.execute(
            select(WishlistItem)
            .where(WishlistItem.device_id == device_id)
            .where(WishlistItem.product_id == product_id)
        )
        return result.scalars().first()

    async def add(self, device_id: UUID, product_id: str) -> WishlistItem:
        """Add item to wishlist."""
        item = WishlistItem(device_id=device_id, product_id=product_id)
        self.session.add(item)
        await self.session.flush()
        return item

    async def remove(self, device_id: UUID, product_id: str) -> bool:
        """Remove item from wishlist. Returns True if item existed."""
        item = await self.get_by_product_id(device_id, product_id)
        if item:
            await self.session.delete(item)
            await self.session.flush()
            return True
        return False

    async def exists(self, device_id: UUID, product_id: str) -> bool:
        """Check if item is in wishlist."""
        item = await self.get_by_product_id(device_id, product_id)
        return item is not None
