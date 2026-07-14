"""Collections API router — curated product collections."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.repositories.brand_repo import BrandRepository
from app.schemas.collection import CollectionResponse, CollectionProductsResponse
from app.services.collections_service import CollectionsService
from app.services.product_cache_service import ProductCacheService, create_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[CollectionResponse])
async def list_collections(
    session: AsyncSession = Depends(get_session),
) -> list[CollectionResponse]:
    """Get all active collections.
    
    Returns curated collections like "Eid", "Mehndi & Sangeet", "Formal Affairs", etc.
    """
    try:
        collections = await CollectionsService.get_all_active_collections(session)
        logger.debug(f"Listed {len(collections)} collections")
        return [
            CollectionResponse(
                id=coll.id,
                title=coll.title,
                subtitle=coll.subtitle,
                description=coll.description,
                image_url=coll.image_url,
                is_active=coll.is_active,
                sort_order=coll.sort_order,
            )
            for coll in collections
        ]
    except Exception as e:
        logger.error(f"Failed to list collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list collections")


@router.get("/{collection_id}", response_model=CollectionProductsResponse)
async def get_collection(
    collection_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    session: AsyncSession = Depends(get_session),
    cache_service: ProductCacheService = Depends(create_cache_service),
) -> CollectionProductsResponse:
    """Get a collection with resolved products.
    
    Returns products matching the collection's filter definition,
    fetched live from the product cache.
    
    Args:
        collection_id: Collection UUID
        page: Page number
        page_size: Results per page
    """
    try:
        # Get collection
        collections = await CollectionsService.get_all_active_collections(session)
        collection = next((c for c in collections if str(c.id) == collection_id), None)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")

        # Get all products from cache
        all_products = []
        brand_repo = BrandRepository(session)
        brands = await brand_repo.get_all_active()

        for brand in brands:
            products = await cache_service.get_or_refresh(brand.slug, brand.domain)
            if products:
                all_products.extend(products)

        logger.debug(
            f"Resolving collection {collection_id} with {len(all_products)} products"
        )

        # Resolve collection products
        result = CollectionsService.resolve_collection_products(
            collection,
            all_products,
            page=page,
            page_size=page_size,
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection {collection_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get collection")
