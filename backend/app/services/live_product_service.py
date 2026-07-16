"""Live verification for cached-search Shopify shortlists."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiohttp

from app.nlp.keyword_matcher import tag_product
from app.schemas.product import Product
from app.shopify.client import BROWSER_USER_AGENT, ShopifyClient
from app.shopify.mapper import html_to_plain_text


@dataclass(frozen=True)
class LiveValidationResult:
    products: list[Product]
    unavailable: int = 0
    failed: int = 0


def _available_option_values(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    definitions = payload.get("options") or []
    names = [
        str(item.get("name", "")).lower() if isinstance(item, dict) else ""
        for item in definitions
    ]
    colors: list[str] = []
    sizes: list[str] = []
    for variant in payload.get("variants") or []:
        if not isinstance(variant, dict) or not variant.get("available", False):
            continue
        values = variant.get("options") or [
            variant.get("option1"), variant.get("option2"), variant.get("option3")
        ]
        for index, raw_value in enumerate(values):
            if raw_value is None or index >= len(names):
                continue
            value = str(raw_value).strip()
            if names[index] in {"color", "colour"} and value not in colors:
                colors.append(value)
            elif names[index] == "size" and value not in sizes:
                sizes.append(value)
    return colors, sizes


def _live_price(payload: dict[str, Any]) -> float | None:
    prices = [
        variant.get("price")
        for variant in payload.get("variants") or []
        if isinstance(variant, dict) and variant.get("available", False)
    ]
    numeric = [float(value) for value in prices if value is not None]
    if not numeric:
        return None
    # Shopify's /products/{handle}.js endpoint returns integer minor units.
    return min(numeric) / 100.0


def _shopify_tags(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("tags") or []
    if isinstance(raw, str):
        return [value.strip() for value in raw.split(",") if value.strip()]
    return [str(value).strip() for value in raw if str(value).strip()]


def _merge_live_product(product: Product, payload: dict[str, Any]) -> Product | None:
    if str(payload.get("id", "")) != product.id.rsplit(":", 1)[-1]:
        return None
    price = _live_price(payload)
    if price is None:
        return None
    colors, sizes = _available_option_values(payload)
    updated = product.model_copy(update={
        "name": str(payload.get("title") or product.name),
        "description": html_to_plain_text(
            str(payload.get("description") or product.description or "")
        ),
        "price": price,
        "category": str(payload.get("type") or product.category or "") or None,
        "shopify_tags": _shopify_tags(payload) or product.shopify_tags,
        "colors": colors or product.colors,
        "sizes": sizes or product.sizes,
        "live_verified": True,
        "live_verified_at": datetime.now(timezone.utc),
    })
    return tag_product(updated)


class LiveProductValidationService:
    def __init__(self, client: ShopifyClient, concurrency: int = 12):
        self._client = client
        self._concurrency = max(1, concurrency)

    async def validate(
        self,
        products: list[Product],
        allowed_domains: set[str],
        limit: int,
    ) -> LiveValidationResult:
        verified: list[Product] = []
        unavailable = 0
        failed = 0
        headers = {"User-Agent": BROWSER_USER_AGENT, "Accept": "application/json"}
        connector = aiohttp.TCPConnector(limit=self._concurrency)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            for offset in range(0, len(products), self._concurrency):
                batch = products[offset:offset + self._concurrency]
                outcomes = await asyncio.gather(*(
                    self._client.fetch_live_product(
                        product.product_url, allowed_domains, session
                    )
                    for product in batch
                ))
                for product, (status, payload) in zip(batch, outcomes):
                    if status == "verified" and payload is not None:
                        merged = _merge_live_product(product, payload)
                        if merged is not None:
                            verified.append(merged)
                        else:
                            failed += 1
                    elif status == "unavailable":
                        unavailable += 1
                    else:
                        failed += 1
                if len(verified) >= limit:
                    break
        return LiveValidationResult(
            products=verified[:limit],
            unavailable=unavailable,
            failed=failed,
        )
