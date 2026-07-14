"""Products API router — search and alternatives endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.repositories.brand_repo import BrandRepository
from app.schemas.product import ProductSearchResponse
from app.services.alternatives_service import AlternativesService
from app.services.product_cache_service import ProductCacheService, create_cache_service
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/search", response_model=ProductSearchResponse)
async def search_products(
    q: Optional[str] = Query(None, description="Search query"),
    occasion: Optional[str] = Query(None, description="Filter by occasion"),
    color: Optional[str] = Query(None, description="Filter by color"),
    size: Optional[str] = Query(None, description="Filter by size"),
    tags: Optional[list[str]] = Query(None, description="Filter by tags (all must match)"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    cache_service: ProductCacheService = Depends(create_cache_service),
    session: AsyncSession = Depends(get_session),
) -> ProductSearchResponse:
    """Search products by keyword and filters.
    
    Supported filters:
    - q: Free-text search (looks in product name and description)
    - occasion: eid, mehndi, wedding, formal, casual
    - color: Partial match on product colors
    - size: Exact match on product sizes
    - tags: Material/style tags (cotton, silk, embroidered, etc.)
    - min_price/max_price: Price range in PKR
    """
    try:
        # Get all brands
        brand_repo = BrandRepository(session)
        brands = await brand_repo.get_all_active()

        # Collect all products from cache
        all_products = []
        for brand in brands:
            products = await cache_service.get_or_refresh(brand.slug, brand.domain)
            if products:
                all_products.extend(products)

        logger.info(
            f"Search query: q={q}, occasion={occasion}, "
            f"total_products={len(all_products)}"
        )

        # Perform search
        result = SearchService.search(
            all_products,
            query=q or "",
            occasion=occasion,
            color=color,
            size=size,
            tags=tags,
            min_price=min_price,
            max_price=max_price,
            page=page,
            page_size=page_size,
        )

        return result
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/{product_id}", response_model=Optional[dict])
async def get_product(
    product_id: str,
    session: AsyncSession = Depends(get_session),
    cache_service: ProductCacheService = Depends(create_cache_service),
) -> Optional[dict]:
    """Get a single product by ID.
    
    Product ID format: "{brand_slug}:{shopify_product_id}"
    Example: "limelight:1234567890"
    """
    try:
        # Parse product ID
        parts = product_id.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid product ID format")

        brand_slug, shopify_id = parts

        # Get brand from database
        brand_repo = BrandRepository(session)
        brand = await brand_repo.get_by_slug(brand_slug)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

        # Get products from cache
        products = await cache_service.get_or_refresh(brand_slug, brand.domain)
        if not products:
            raise HTTPException(status_code=404, detail="Products not found for brand")

        # Find the specific product
        product = next((p for p in products if p.id == product_id), None)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        return product.dict() if hasattr(product, "dict") else product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get product {product_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get product")


@router.get("/{product_id}/alternatives", response_model=ProductSearchResponse)
async def get_alternatives(
    product_id: str,
    exclude_same_brand: bool = Query(False, description="Exclude same brand"),
    limit: int = Query(10, ge=1, le=50, description="Max alternatives to consider"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Results per page"),
    session: AsyncSession = Depends(get_session),
    cache_service: ProductCacheService = Depends(create_cache_service),
) -> ProductSearchResponse:
    """Get similar products (alternatives) for a given product.
    
    Uses tag-based similarity: materials, styles, price range, colors.
    """
    try:
        # Parse product ID
        parts = product_id.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid product ID format")

        brand_slug, _ = parts

        # Get reference product
        brand_repo = BrandRepository(session)
        brand = await brand_repo.get_by_slug(brand_slug)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

        products = await cache_service.get_or_refresh(brand_slug, brand.domain)
        if not products:
            raise HTTPException(status_code=404, detail="Products not found")

        reference = next((p for p in products if p.id == product_id), None)
        if not reference:
            raise HTTPException(status_code=404, detail="Product not found")

        # Get all products from all brands for recommendations
        all_brands = await brand_repo.get_all_active()
        all_products = []
        for b in all_brands:
            prods = await cache_service.get_or_refresh(b.slug, b.domain)
            if prods:
                all_products.extend(prods)

        # Get alternatives
        result = AlternativesService.get_alternatives_response(
            reference,
            all_products,
            exclude_same_brand=exclude_same_brand,
            limit=limit,
            page=page,
            page_size=page_size,
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alternatives for {product_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get alternatives")
