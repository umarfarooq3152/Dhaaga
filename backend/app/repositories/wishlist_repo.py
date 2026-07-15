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
        """Get all anonymous (non-account) wishlist items for a device."""
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

    # --- Account-scoped variants (logged in) ---

    async def get_all_for_user(self, user_id: UUID) -> list[WishlistItem]:
        """Get all wishlist items for a logged-in user's account, across
        whichever devices added them."""
        result = await self.session.execute(
            select(WishlistItem)
            .where(WishlistItem.user_id == user_id)
            .order_by(WishlistItem.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_product_id_for_user(
        self, user_id: UUID, product_id: str
    ) -> Optional[WishlistItem]:
        result = await self.session.execute(
            select(WishlistItem)
            .where(WishlistItem.user_id == user_id)
            .where(WishlistItem.product_id == product_id)
        )
        return result.scalars().first()

    async def add_for_user(
        self, user_id: UUID, device_id: UUID, product_id: str
    ) -> WishlistItem:
        """Add an item to a logged-in user's account-scoped wishlist.
        device_id is still recorded (the row's primary key requires it),
        but reads/removes for a logged-in shopper key off user_id so the
        item is visible from any device once they're signed in."""
        item = WishlistItem(device_id=device_id, product_id=product_id, user_id=user_id)
        self.session.add(item)
        await self.session.flush()
        return item

    async def remove_for_user(self, user_id: UUID, product_id: str) -> bool:
        item = await self.get_by_product_id_for_user(user_id, product_id)
        if item:
            await self.session.delete(item)
            await self.session.flush()
            return True
        return False

    async def exists_for_user(self, user_id: UUID, product_id: str) -> bool:
        item = await self.get_by_product_id_for_user(user_id, product_id)
        return item is not None

    async def claim_device_wishlist(self, device_id: UUID, user_id: UUID) -> None:
        """On signup/login, fold this device's anonymous wishlist items
        into the user's account so they aren't lost. An item the account
        already has (added from a different device previously) is just
        dropped as a duplicate rather than causing a constraint error."""
        existing = await self.session.execute(
            select(WishlistItem.product_id).where(WishlistItem.user_id == user_id)
        )
        existing_ids = {row[0] for row in existing.all()}

        anon_items = await self.session.execute(
            select(WishlistItem)
            .where(WishlistItem.device_id == device_id)
            .where(WishlistItem.user_id.is_(None))
        )
        for item in anon_items.scalars().all():
            if item.product_id in existing_ids:
                await self.session.delete(item)
            else:
                item.user_id = user_id
                existing_ids.add(item.product_id)
        await self.session.flush()
