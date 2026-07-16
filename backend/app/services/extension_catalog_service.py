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
    """Fetch a broad live catalog and retain a stale safety copy in Redis."""

    CACHE_KEY = "extension:catalog:{domain}:{limit}"
    STALE_CACHE_KEY = "extension:catalog:stale:{domain}:{limit}"

    def __init__(
        self,
        redis_client,
        shopify_client: ShopifyClient,
        max_products: int = 5000,
        ttl_seconds: int = 900,
    ):
        self._redis = redis_client
        self._shopify = shopify_client
        self._max_products = min(max(max_products, 1), 5000)
        self._ttl_seconds = max(ttl_seconds, 60)
        self._stale_ttl_seconds = max(self._ttl_seconds * 24, 21600)

    async def get_catalog(self, domain: str) -> ExtensionCatalog:
        key = self.CACHE_KEY.format(domain=domain, limit=self._max_products)
        stale_key = self.STALE_CACHE_KEY.format(domain=domain, limit=self._max_products)
        cached = await self._read_cache(key)
        if cached is not None:
            return cached

        # Probe one item beyond the configured limit. This distinguishes an
        # exactly-full catalog from a genuinely truncated one instead of
        # marking every exact boundary (500, 1000, ...) as partial.
        probe_limit = self._max_products + 1
        max_pages = (probe_limit + 249) // 250
        products = await self._shopify.fetch_all_products(
            domain,
            max_pages=max_pages,
            max_products=probe_limit,
        )
        if not products:
            stale = await self._read_cache(stale_key)
            if stale is not None:
                logger.warning("Using stale extension catalog for %s after fetch failure", domain)
                return stale
            raise CatalogUnavailableError(
                "The store catalog could not be read or contained no products."
            )

        capped = len(products) > self._max_products
        catalog = ExtensionCatalog(products=products[: self._max_products], capped=capped)
        await self._write_cache(key, catalog, self._ttl_seconds)
        await self._write_cache(stale_key, catalog, self._stale_ttl_seconds)
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

    async def _write_cache(self, key: str, catalog: ExtensionCatalog, ttl_seconds: int) -> None:
        try:
            await self._redis.setex(
                key,
                ttl_seconds,
                json.dumps({"products": catalog.products, "capped": catalog.capped}),
            )
        except Exception as error:
            # Catalog retrieval should still succeed when Redis is unavailable.
            logger.warning("Extension catalog cache write failed: %s", error)


class CatalogUnavailableError(RuntimeError):
    pass
