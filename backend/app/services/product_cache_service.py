"""Product cache service with Redis backend and self-healing fallback."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis

from app.config import get_settings
from app.nlp.keyword_matcher import tag_products_batch
from app.schemas.product import Product
from app.shopify.client import ShopifyClient
from app.shopify.mapper import map_shopify_batch

logger = logging.getLogger(__name__)


class ProductCacheService:
    """Manages Redis-backed product cache with refresh orchestration."""

    CACHE_TTL_SECONDS = 1800  # 30 minutes default
    REFRESH_LOCK_TTL_SECONDS = 300  # 5 minute lock to prevent thundering herd
    CACHE_KEY_BRAND = "products:{brand_slug}"
    CACHE_KEY_REFRESH_LOCK = "refresh_lock:{brand_slug}"

    def __init__(self, redis_client: redis.Redis):
        """Initialize cache service.
        
        Args:
            redis_client: Redis async client
        """
        self.redis = redis_client
        self.shopify_client = ShopifyClient()

    async def get_cached_products(self, brand_slug: str) -> list[Product] | None:
        """Retrieve cached products for a brand.
        
        Args:
            brand_slug: Brand slug (e.g., 'limelight')
            
        Returns:
            List of Product objects or None if not cached
        """
        try:
            cache_key = self.CACHE_KEY_BRAND.format(brand_slug=brand_slug)
            cached_data = await self.redis.get(cache_key)

            if not cached_data:
                logger.debug(f"Cache miss for {brand_slug}")
                return None

            # Deserialize products
            products_data = json.loads(cached_data)
            products = [Product(**p) for p in products_data]
            logger.debug(f"Cache hit for {brand_slug}: {len(products)} products")
            return products
        except Exception as e:
            logger.error(f"Failed to retrieve cached products for {brand_slug}: {e}")
            return None

    async def set_cached_products(
        self, brand_slug: str, products: list[Product], ttl: int = CACHE_TTL_SECONDS
    ) -> bool:
        """Store products in cache.
        
        Args:
            brand_slug: Brand slug
            products: List of Product objects
            ttl: Cache TTL in seconds
            
        Returns:
            True if successful
        """
        try:
            cache_key = self.CACHE_KEY_BRAND.format(brand_slug=brand_slug)
            products_data = [p.dict() if hasattr(p, "dict") else p for p in products]
            await self.redis.setex(
                cache_key,
                ttl,
                json.dumps(products_data),
            )
            logger.info(f"Cached {len(products)} products for {brand_slug}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache products for {brand_slug}: {e}")
            return False

    async def _acquire_refresh_lock(self, brand_slug: str) -> bool:
        """Acquire a refresh lock to prevent concurrent refreshes (thundering herd).
        
        Args:
            brand_slug: Brand slug
            
        Returns:
            True if lock acquired, False if already locked
        """
        lock_key = self.CACHE_KEY_REFRESH_LOCK.format(brand_slug=brand_slug)
        try:
            # SET NX: only set if not exists
            result = await self.redis.set(
                lock_key,
                "1",
                ex=self.REFRESH_LOCK_TTL_SECONDS,
                nx=True,
            )
            return result is not None
        except Exception as e:
            logger.error(f"Failed to acquire refresh lock for {brand_slug}: {e}")
            return False

    async def _release_refresh_lock(self, brand_slug: str) -> None:
        """Release the refresh lock so the next call isn't blocked until TTL expiry."""
        lock_key = self.CACHE_KEY_REFRESH_LOCK.format(brand_slug=brand_slug)
        try:
            await self.redis.delete(lock_key)
        except Exception as e:
            logger.error(f"Failed to release refresh lock for {brand_slug}: {e}")

    async def refresh_brand_products(
        self, brand_slug: str, domain: str
    ) -> list[Product] | None:
        """Refresh products for a brand from Shopify with locking.
        
        Args:
            brand_slug: Brand slug (e.g., 'limelight')
            domain: Brand domain (e.g., 'limelight.pk')
            
        Returns:
            List of refreshed products or None on failure
        """
        # Try to acquire lock (prevent thundering herd)
        if not await self._acquire_refresh_lock(brand_slug):
            logger.debug(f"Refresh already in progress for {brand_slug}")
            # Return cached data while refresh is in progress
            return await self.get_cached_products(brand_slug)

        try:
            logger.info(f"Refreshing products for {brand_slug}")

            # Fetch from Shopify
            shopify_products = await self.shopify_client.fetch_all_products(domain)

            if not shopify_products:
                logger.warning(f"No products fetched from Shopify for {brand_slug}")
                # Return cached data as fallback
                return await self.get_cached_products(brand_slug)

            # Map to Product schema
            products = map_shopify_batch(shopify_products, brand_slug, domain)

            if not products:
                logger.warning(f"No products mapped for {brand_slug}")
                return await self.get_cached_products(brand_slug)

            # Tag products with occasion/material
            tagged_products = tag_products_batch(products)

            # Cache the results
            await self.set_cached_products(brand_slug, tagged_products)

            logger.info(
                f"Successfully refreshed {len(tagged_products)} products "
                f"for {brand_slug}"
            )
            return tagged_products
        except Exception as e:
            logger.error(
                f"Failed to refresh products for {brand_slug}: {e}",
                exc_info=True,
            )
            # Self-healing fallback: return cached data
            return await self.get_cached_products(brand_slug)
        finally:
            # Release explicitly rather than relying solely on the lock's
            # TTL — otherwise a cleared/expired product cache stays stuck
            # returning empty for up to the full lock TTL, since a "held"
            # lock makes get_or_refresh skip straight to (now-empty) cache.
            await self._release_refresh_lock(brand_slug)

    async def get_or_refresh(
        self, brand_slug: str, domain: str
    ) -> list[Product] | None:
        """Get cached products or refresh if missing/expired.
        
        Args:
            brand_slug: Brand slug
            domain: Brand domain
            
        Returns:
            List of products or None
        """
        cached = await self.get_cached_products(brand_slug)
        if cached:
            return cached

        # Cache miss or expired - refresh
        return await self.refresh_brand_products(brand_slug, domain)

    async def refresh_all_brands(
        self, brands: list[dict[str, str]]
    ) -> dict[str, int]:
        """Refresh all brands sequentially (called by background job).
        
        Args:
            brands: List of {slug, domain} dicts
            
        Returns:
            Dict with {brand_slug: product_count}
        """
        results = {}
        for brand in brands:
            slug = brand.get("slug")
            domain = brand.get("domain")
            if not slug or not domain:
                continue

            try:
                products = await self.refresh_brand_products(slug, domain)
                results[slug] = len(products) if products else 0
            except Exception as e:
                logger.error(f"Failed to refresh {slug}: {e}")
                results[slug] = 0

            # Small delay to avoid hammering Shopify
            await asyncio.sleep(1)

        logger.info(f"Refresh cycle complete: {results}")
        return results


async def create_cache_service() -> ProductCacheService:
    """Factory to create cache service with Redis connection."""
    settings = get_settings()
    redis_client = await redis.from_url(settings.redis_url)
    return ProductCacheService(redis_client)


async def close_cache_service(service: ProductCacheService):
    """Cleanup cache service (close Redis connection)."""
    if service and service.redis:
        await service.redis.close()
