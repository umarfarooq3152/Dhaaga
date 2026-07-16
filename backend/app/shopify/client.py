"""Shopify API client for fetching products from brand storefronts."""

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

# aiohttp's default User-Agent ("Python/3.x aiohttp/3.x") is blocked with a 429
# by Shopify/Cloudflare's bot protection on every storefront tested — curl and
# a real browser UA succeed against the identical URL. A browser-like UA is
# required for /products.json to return data at all.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class ShopifyClient:
    """Async HTTP client for Shopify's public products JSON endpoint."""

    def __init__(self, timeout: int = 30):
        """Initialize Shopify client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    async def fetch_products(
        self, domain: str, limit: int = 250, page: int = 1, retries: int = 3
    ) -> dict[str, Any]:
        """Fetch products from a Shopify storefront.
        
        Args:
            domain: Brand domain (e.g., 'limelight.pk')
            limit: Max products per page (max 250)
            page: One-indexed page number. Shopify's public products endpoint
                supports page-based pagination; it does not include a cursor
                in the response body.
            
        Returns:
            Response dict with a products list
            
        Raises:
            aiohttp.ClientError: On network/HTTP errors
        """
        url = f"https://{domain}/products.json"
        params = {"limit": min(max(limit, 1), 250), "page": max(page, 1)}

        headers = {"User-Agent": BROWSER_USER_AGENT}
        for attempt in range(max(1, retries)):
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, params=params, timeout=self.timeout) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        if resp.status == 404:
                            logger.warning(f"Shopify endpoint not found for {domain}")
                            return {"products": []}
                        if resp.status not in {429, 500, 502, 503, 504}:
                            logger.error(f"Shopify API error for {domain}: status={resp.status}")
                            return {"products": []}
                        logger.warning(
                            "Retryable Shopify response for %s page %s: %s (attempt %s/%s)",
                            domain, page, resp.status, attempt + 1, retries,
                        )
            except (asyncio.TimeoutError, aiohttp.ClientError) as error:
                logger.warning(
                    "Retryable Shopify failure for %s page %s: %s (attempt %s/%s)",
                    domain, page, error, attempt + 1, retries,
                )
            if attempt + 1 < retries:
                await asyncio.sleep(min(2 ** attempt, 4))
        logger.error("Shopify page exhausted retries for %s page %s", domain, page)
        return {"products": [], "_fetch_failed": True}

    async def fetch_all_products(
        self, domain: str, max_pages: int = 40, max_products: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all products from a brand, handling pagination.
        
        Args:
            domain: Brand domain (e.g., 'limelight.pk')
            max_pages: Max number of pages to fetch (safety limit)
            
        Returns:
            List of all product objects
        """
        all_products = []
        page_count = 0
        seen_ids: set[str] = set()
        page_size = 250

        while page_count < max_pages:
            response = await self.fetch_products(
                domain, limit=page_size, page=page_count + 1
            )
            if response.get("_fetch_failed"):
                # Never replace a complete cached snapshot with a partial
                # catalog after a transient page failure.
                logger.warning("Keeping prior catalog snapshot for %s after page failure", domain)
                return []
            products = response.get("products", [])

            if not isinstance(products, list) or not products:
                break

            new_products = []
            for product in products:
                product_id = str(product.get("id", "")) if isinstance(product, dict) else ""
                if not product_id or product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                new_products.append(product)

            # A storefront returning the same page repeatedly must not create
            # an unbounded loop or duplicate catalog entries.
            if not new_products:
                break

            all_products.extend(new_products)
            page_count += 1

            if max_products is not None and len(all_products) >= max_products:
                all_products = all_products[:max_products]
                break

            if len(products) < page_size:
                break

            logger.debug(
                f"Fetched page {page_count} from {domain}: "
                f"{len(new_products)} new products, "
                f"total: {len(all_products)}"
            )

        logger.info(
            f"Fetched {len(all_products)} total products from {domain} "
            f"in {page_count} pages"
        )
        return all_products

    async def fetch_live_product(
        self,
        product_url: str,
        allowed_domains: set[str],
        session: aiohttp.ClientSession,
    ) -> tuple[str, dict[str, Any] | None]:
        """Fetch one current Shopify product with an allowlisted destination."""
        parsed = urlparse(product_url)
        host = (parsed.hostname or "").lower()
        allowed = {domain.lower().removeprefix("www.") for domain in allowed_domains}
        if (
            parsed.scheme not in {"http", "https"}
            or host.removeprefix("www.") not in allowed
            or "/products/" not in parsed.path
        ):
            return "failed", None
        handle = parsed.path.split("/products/", 1)[1].split("/", 1)[0]
        handle = handle.removesuffix(".js").removesuffix(".json")
        if not handle or not all(char.isalnum() or char in "-_" for char in handle):
            return "failed", None
        url = f"https://{host}/products/{handle}.js"
        try:
            async with session.get(url, timeout=self.timeout) as response:
                response_host = (response.url.host or "").lower().removeprefix("www.")
                if response_host not in allowed:
                    return "failed", None
                if response.status in {404, 410}:
                    return "unavailable", None
                if response.status != 200:
                    return "failed", None
                payload = await response.json(content_type=None)
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError):
            return "failed", None
        if not isinstance(payload, dict):
            return "failed", None
        variants = payload.get("variants") or []
        has_available_variant = any(
            isinstance(variant, dict) and variant.get("available", False)
            for variant in variants
        )
        if not payload.get("available", has_available_variant) or not has_available_variant:
            return "unavailable", payload
        return "verified", payload
