"""Wishlist API router — manage device wishlists."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.repositories.device_repo import DeviceRepository
from app.repositories.wishlist_repo import WishlistRepository
from app.repositories.brand_repo import BrandRepository
from app.schemas.wishlist import WishlistResponse, WishlistItemResponse
from app.services.product_cache_service import ProductCacheService, create_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=WishlistResponse)
async def get_wishlist(
    device_id: UUID = Header(..., description="Device ID from X-Device-Id header"),
    session: AsyncSession = Depends(get_session),
    cache_service: ProductCacheService = Depends(create_cache_service),
) -> WishlistResponse:
    """Get device wishlist with product details.
    
    Requires X-Device-Id header with device UUID.
    Returns wishlist items with full product information from cache.
    """
    try:
        # Verify device exists
        device_repo = DeviceRepository(session)
        device = await device_repo.get_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        # Get wishlist items
        wishlist_repo = WishlistRepository(session)
        items = await wishlist_repo.get_all(device_id)

        # Hydrate products from cache
        brand_repo = BrandRepository(session)
        hydrated_items = []

        for item in items:
            # Parse product ID to get brand
            parts = item.product_id.split(":")
            if len(parts) == 2:
                brand_slug = parts[0]
                brand = await brand_repo.get_by_slug(brand_slug)
                if brand:
                    products = await cache_service.get_or_refresh(
                        brand_slug, brand.domain
                    )
                    if products:
                        product = next(
                            (p for p in products if p.id == item.product_id), None
                        )
                        if product:
                            hydrated_items.append(
                                WishlistItemResponse(
                                    product=product,
                                    added_at=item.created_at,
                                )
                            )

        logger.debug(f"Retrieved wishlist for device {device_id}: {len(hydrated_items)} items")
        return WishlistResponse(items=hydrated_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get wishlist for {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get wishlist")


@router.post("/{product_id}", response_model=dict)
async def add_to_wishlist(
    product_id: str,
    device_id: UUID = Header(..., description="Device ID"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Add a product to wishlist.
    
    Args:
        product_id: Product ID in format "{brand_slug}:{shopify_product_id}"
        device_id: Device UUID (from X-Device-Id header)
        
    Returns:
        { success: true, message: "Added to wishlist" }
    """
    try:
        # Verify device exists
        device_repo = DeviceRepository(session)
        device = await device_repo.get_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        # Add to wishlist
        wishlist_repo = WishlistRepository(session)
        exists = await wishlist_repo.exists(device_id, product_id)
        if exists:
            return {"success": False, "message": "Already in wishlist"}

        await wishlist_repo.add(device_id, product_id)

        # Update device last_seen
        await device_repo.update_last_seen(device_id)

        logger.info(f"Added {product_id} to wishlist for device {device_id}")
        return {"success": True, "message": "Added to wishlist"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add to wishlist: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add to wishlist")


@router.delete("/{product_id}", response_model=dict)
async def remove_from_wishlist(
    product_id: str,
    device_id: UUID = Header(..., description="Device ID"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Remove a product from wishlist.
    
    Args:
        product_id: Product ID
        device_id: Device UUID (from X-Device-Id header)
        
    Returns:
        { success: true, message: "Removed from wishlist" }
    """
    try:
        # Verify device exists
        device_repo = DeviceRepository(session)
        device = await device_repo.get_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        # Remove from wishlist
        wishlist_repo = WishlistRepository(session)
        await wishlist_repo.remove(device_id, product_id)

        # Update device last_seen
        await device_repo.update_last_seen(device_id)

        logger.info(f"Removed {product_id} from wishlist for device {device_id}")
        return {"success": True, "message": "Removed from wishlist"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove from wishlist: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove from wishlist")
