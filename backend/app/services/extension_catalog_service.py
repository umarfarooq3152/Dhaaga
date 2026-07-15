"""Small, bounded Shopify catalog cache for the browser extension."""

import json
import logging
from dataclasses import dataclass

from app.shopify.client import ShopifyClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtensionCatalog:
    products: list[dict]
    capped: bool


class ExtensionCatalogService:
    """Fetch at most the configured MVP cap and cache the raw variant data."""

    CACHE_KEY = "extension:catalog:{domain}:{limit}"

    def __init__(
        self,
        redis_client,
        shopify_client: ShopifyClient,
        max_products: int = 500,
        ttl_seconds: int = 900,
    ):
        self._redis = redis_client
        self._shopify = shopify_client
        self._max_products = min(max(max_products, 1), 1000)
        self._ttl_seconds = max(ttl_seconds, 60)

    async def get_catalog(self, domain: str) -> ExtensionCatalog:
        key = self.CACHE_KEY.format(domain=domain, limit=self._max_products)
        cached = await self._read_cache(key)
        if cached is not None:
            return cached

        max_pages = (self._max_products + 249) // 250
        products = await self._shopify.fetch_all_products(
            domain,
            max_pages=max_pages,
            max_products=self._max_products,
        )
        if not products:
            raise CatalogUnavailableError(
                "The store catalog could not be read or contained no products."
            )

        # If the final allowed page was full, more products may exist.
        capped = len(products) >= self._max_products
        catalog = ExtensionCatalog(products=products, capped=capped)
        await self._write_cache(key, catalog)
        return catalog

    async def _read_cache(self, key: str) -> ExtensionCatalog | None:
        try:
            raw = await self._redis.get(key)
            if not raw:
                return None
            payload = json.loads(raw)
            products = payload.get("products")
            if not isinstance(products, list) or not products:
                return None
            return ExtensionCatalog(
                products=[item for item in products if isinstance(item, dict)],
                capped=bool(payload.get("capped")),
            )
        except Exception as error:
            logger.warning("Extension catalog cache read failed: %s", error)
            return None

    async def _write_cache(self, key: str, catalog: ExtensionCatalog) -> None:
        try:
            await self._redis.setex(
                key,
                self._ttl_seconds,
                json.dumps({"products": catalog.products, "capped": catalog.capped}),
            )
        except Exception as error:
            # Catalog retrieval should still succeed when Redis is unavailable.
            logger.warning("Extension catalog cache write failed: %s", error)


class CatalogUnavailableError(RuntimeError):
    pass
