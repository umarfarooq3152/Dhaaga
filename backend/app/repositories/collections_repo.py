"""Collections repository — data access for curated collections."""

from typing import Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.collections import Collection


class CollectionsRepository:
    """Repository for collections table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_active(self) -> list[Collection]:
        """Get all active collections, ordered by sort_order."""
        result = await self.session.execute(
            select(Collection)
            .where(Collection.is_active == True)
            .order_by(Collection.sort_order)
        )
        return result.scalars().all()

    async def get_by_id(self, collection_id: UUID) -> Optional[Collection]:
        """Get collection by ID."""
        return await self.session.get(Collection, collection_id)

    async def create(
        self,
        title: str,
        filter_definition: dict[str, Any],
        subtitle: Optional[str] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None,
        sort_order: int = 0,
    ) -> Collection:
        """Create a new collection."""
        collection = Collection(
            title=title,
            subtitle=subtitle,
            description=description,
            image_url=image_url,
            filter_definition=filter_definition,
            is_active=True,
            sort_order=sort_order,
        )
        self.session.add(collection)
        await self.session.flush()
        return collection

    async def update(
        self,
        collection_id: UUID,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        description: Optional[str] = None,
        filter_definition: Optional[dict[str, Any]] = None,
        sort_order: Optional[int] = None,
    ) -> None:
        """Update collection fields."""
        collection = await self.get_by_id(collection_id)
        if collection:
            if title is not None:
                collection.title = title
            if subtitle is not None:
                collection.subtitle = subtitle
            if description is not None:
                collection.description = description
            if filter_definition is not None:
                collection.filter_definition = filter_definition
            if sort_order is not None:
                collection.sort_order = sort_order
            await self.session.flush()

    async def set_active_status(self, collection_id: UUID, is_active: bool) -> None:
        """Update collection active status."""
        collection = await self.get_by_id(collection_id)
        if collection:
            collection.is_active = is_active
            await self.session.flush()
