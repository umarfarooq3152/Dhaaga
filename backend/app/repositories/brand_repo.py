"""Brand repository — data access for brands."""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.brand import Brand


class BrandRepository:
    """Repository for brand_registry table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_active(self) -> list[Brand]:
        """Get all active brands."""
        result = await self.session.execute(
            select(Brand).where(Brand.is_active == True).order_by(Brand.name)
        )
        return result.scalars().all()

    async def get_by_slug(self, slug: str) -> Optional[Brand]:
        """Get brand by slug."""
        result = await self.session.execute(
            select(Brand).where(Brand.slug == slug)
        )
        return result.scalars().first()

    async def get_by_id(self, brand_id: UUID) -> Optional[Brand]:
        """Get brand by ID."""
        return await self.session.get(Brand, brand_id)

    async def create(self, name: str, slug: str, domain: str, logo_url: Optional[str] = None) -> Brand:
        """Create a new brand."""
        brand = Brand(
            name=name,
            slug=slug,
            domain=domain,
            logo_url=logo_url,
            is_active=True,
        )
        self.session.add(brand)
        await self.session.flush()
        return brand

    async def update_active_status(self, brand_id: UUID, is_active: bool) -> None:
        """Update brand active status."""
        brand = await self.get_by_id(brand_id)
        if brand:
            brand.is_active = is_active
            await self.session.flush()
