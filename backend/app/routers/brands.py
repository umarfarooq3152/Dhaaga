"""Brands API router — brand discovery endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.repositories.brand_repo import BrandRepository
from app.schemas.brand import BrandResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=list[BrandResponse])
async def list_brands(
    session: AsyncSession = Depends(get_session),
) -> list[BrandResponse]:
    """Get all active brands.
    
    Returns the 16 Tier-1 Pakistani clothing brands available in Dhaaga.
    """
    try:
        repo = BrandRepository(session)
        brands = await repo.get_all_active()
        logger.debug(f"Listed {len(brands)} brands")
        return [BrandResponse.from_orm(b) for b in brands]
    except Exception as e:
        logger.error(f"Failed to list brands: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list brands")


@router.get("/{slug}", response_model=BrandResponse)
async def get_brand(
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> BrandResponse:
    """Get a specific brand by slug.
    
    Args:
        slug: Brand slug (e.g., 'limelight', 'alkaram-studio')
        
    Returns:
        Brand details with name, domain, logo_url
    """
    try:
        repo = BrandRepository(session)
        brand = await repo.get_by_slug(slug)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        return BrandResponse.from_orm(brand)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get brand {slug}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get brand")
