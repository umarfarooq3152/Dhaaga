"""Shopify API client for fetching products from brand storefronts."""

import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class ShopifyClient:
    """Async HTTP client for Shopify's public products JSON endpoint."""

    def __init__(self, timeout: int = 30):
        """Initialize Shopify client.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    async def fetch_products(
        self, domain: str, limit: int = 250, cursor: str | None = None
    ) -> dict[str, Any]:
        """Fetch products from a Shopify storefront.
        
        Args:
            domain: Brand domain (e.g., 'limelight.pk')
            limit: Max products per page (max 250)
            cursor: Pagination cursor for next page
            
        Returns:
            Response dict with keys: products, cursor (if paginated)
            
        Raises:
            aiohttp.ClientError: On network/HTTP errors
        """
        url = f"https://{domain}/products.json"
        params = {"limit": min(limit, 250)}
        if cursor:
            params["cursor"] = cursor

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 404:
                        logger.warning(f"Shopify endpoint not found for {domain}")
                        return {"products": []}
                    else:
                        logger.error(
                            f"Shopify API error for {domain}: "
                            f"status={resp.status}"
                        )
                        return {"products": []}
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching products from {domain}")
            return {"products": []}
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch from {domain}: {e}")
            return {"products": []}

    async def fetch_all_products(
        self, domain: str, max_pages: int = 20
    ) -> list[dict[str, Any]]:
        """Fetch all products from a brand, handling pagination.
        
        Args:
            domain: Brand domain (e.g., 'limelight.pk')
            max_pages: Max number of pages to fetch (safety limit)
            
        Returns:
            List of all product objects
        """
        all_products = []
        cursor = None
        page_count = 0

        while page_count < max_pages:
            response = await self.fetch_products(domain, cursor=cursor)
            products = response.get("products", [])

            if not products:
                break

            all_products.extend(products)
            page_count += 1

            # Check for pagination cursor
            cursor = response.get("cursor")
            if not cursor:
                break

            logger.debug(
                f"Fetched page {page_count} from {domain}: "
                f"{len(products)} products, "
                f"total: {len(all_products)}"
            )

        logger.info(
            f"Fetched {len(all_products)} total products from {domain} "
            f"in {page_count} pages"
        )
        return all_products

