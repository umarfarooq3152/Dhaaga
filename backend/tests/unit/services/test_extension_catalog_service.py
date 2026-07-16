import json
from unittest.mock import AsyncMock

import pytest

from app.services.extension_catalog_service import (
    CatalogUnavailableError,
    ExtensionCatalogService,
)


@pytest.mark.asyncio
async def test_reads_valid_cached_catalog_without_fetching():
    redis = AsyncMock()
    redis.get.return_value = json.dumps({"products": [{"id": 1}], "capped": True})
    shopify = AsyncMock()
    service = ExtensionCatalogService(redis, shopify, max_products=500)

    result = await service.get_catalog("outfitters.com.pk")

    assert result.products == [{"id": 1}]
    assert result.capped is True
    shopify.fetch_all_products.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetches_two_pages_writes_cache_and_marks_cap():
    redis = AsyncMock()
    redis.get.return_value = None
    shopify = AsyncMock()
    shopify.fetch_all_products.return_value = [{"id": value} for value in range(501)]
    service = ExtensionCatalogService(redis, shopify, max_products=500, ttl_seconds=600)

    result = await service.get_catalog("outfitters.com.pk")

    assert len(result.products) == 500
    assert result.capped is True
    shopify.fetch_all_products.assert_awaited_once_with(
        "outfitters.com.pk", max_pages=3, max_products=501
    )
    assert redis.setex.await_count == 2


@pytest.mark.asyncio
async def test_exact_limit_is_not_incorrectly_marked_capped():
    redis = AsyncMock()
    redis.get.return_value = None
    shopify = AsyncMock()
    shopify.fetch_all_products.return_value = [{"id": value} for value in range(500)]
    service = ExtensionCatalogService(redis, shopify, max_products=500)

    result = await service.get_catalog("outfitters.com.pk")

    assert len(result.products) == 500
    assert result.capped is False


@pytest.mark.asyncio
async def test_failed_refresh_uses_stale_catalog():
    redis = AsyncMock()
    redis.get.side_effect = [
        None,
        json.dumps({"products": [{"id": "stale"}], "capped": False}),
    ]
    shopify = AsyncMock()
    shopify.fetch_all_products.return_value = []
    service = ExtensionCatalogService(redis, shopify, max_products=500)

    result = await service.get_catalog("outfitters.com.pk")

    assert result.products == [{"id": "stale"}]
    assert result.capped is False


@pytest.mark.asyncio
async def test_empty_fetch_is_catalog_unavailable_even_if_cache_fails():
    redis = AsyncMock()
    redis.get.side_effect = RuntimeError("redis offline")
    shopify = AsyncMock()
    shopify.fetch_all_products.return_value = []
    service = ExtensionCatalogService(redis, shopify)
    with pytest.raises(CatalogUnavailableError):
        await service.get_catalog("outfitters.com.pk")
