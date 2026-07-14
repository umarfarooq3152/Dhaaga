"""Collections service for curated product collections with live filter resolution."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.collections import Collection as CollectionModel
from app.repositories.collections_repo import CollectionsRepository
from app.schemas.collection import CollectionProductsResponse
from app.schemas.product import Product
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


class CollectionsService:
    """Manages product collections with live filter resolution."""

    @staticmethod
    def resolve_collection_filters(
        filter_definition: dict[str, Any],
    ) -> tuple[str | None, str | None, list[str] | None, list[str] | None, float | None, float | None]:
        """Parse collection filter definition into search parameters.
        
        Args:
            filter_definition: Collection filter JSON
            
        Returns:
            Tuple of (query, occasion, colors[], tags[], min_price, max_price)
        """
        query = filter_definition.get("query", "")
        occasion = filter_definition.get("occasion")
        colors = filter_definition.get("colors")
        tags = filter_definition.get("tags")
        min_price = filter_definition.get("min_price")
        max_price = filter_definition.get("max_price")

        return (query, occasion, colors, tags, min_price, max_price)

    @staticmethod
    def resolve_collection_products(
        collection: CollectionModel,
        all_products: list[Product],
        page: int = 1,
        page_size: int = 20,
    ) -> CollectionProductsResponse:
        """Resolve collection products by applying filters to live product cache.
        
        Args:
            collection: Collection model with filter definition
            all_products: All available products from cache
            page: Page number
            page_size: Results per page
            
        Returns:
            Paginated collection products response
        """
        if not collection.filter_definition:
            # No filters = show all products
            products = all_products
        else:
            # Parse and apply filters
            query, occasion, colors, tags, min_price, max_price = (
                CollectionsService.resolve_collection_filters(
                    collection.filter_definition
                )
            )

            # Use search service to apply filters
            result = SearchService.search(
                all_products,
                query=query or "",
                occasion=occasion,
                color=colors[0] if colors else None,  # First color for filtering
                tags=tags,
                min_price=min_price,
                max_price=max_price,
                page=page,
                page_size=page_size,
            )

            return CollectionProductsResponse(
                id=str(collection.id),
                title=collection.title,
                subtitle=collection.subtitle,
                description=collection.description,
                image_url=collection.image_url,
                items=result.items,
                total=result.total,
                page=result.page,
                page_size=result.page_size,
                has_more=result.has_more,
            )

        # Pagination
        total = len(products)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = products[start_idx:end_idx]

        return CollectionProductsResponse(
            id=str(collection.id),
            title=collection.title,
            subtitle=collection.subtitle,
            description=collection.description,
            image_url=collection.image_url,
            items=paginated,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end_idx < total,
        )

    @staticmethod
    async def get_all_active_collections(
        session: AsyncSession,
    ) -> list[CollectionModel]:
        """Fetch all active collections from database.
        
        Args:
            session: Database session
            
        Returns:
            List of active Collection models
        """
        repo = CollectionsRepository(session)
        return await repo.get_all_active()

    @staticmethod
    async def resolve_all_collections(
        session: AsyncSession,
        all_products: list[Product],
        page_size: int = 20,
    ) -> list[CollectionProductsResponse]:
        """Resolve all active collections with live products.
        
        Args:
            session: Database session
            all_products: All available products
            page_size: Results per page
            
        Returns:
            List of resolved CollectionProductsResponse
        """
        collections = await CollectionsService.get_all_active_collections(session)

        resolved = [
            CollectionsService.resolve_collection_products(
                coll,
                all_products,
                page=1,
                page_size=page_size,
            )
            for coll in collections
        ]

        return resolved
