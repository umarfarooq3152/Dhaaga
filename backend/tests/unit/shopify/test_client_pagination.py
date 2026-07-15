from unittest.mock import AsyncMock

import pytest

from app.shopify.client import ShopifyClient


@pytest.mark.asyncio
async def test_page_pagination_deduplicates_and_stops_on_short_page():
    client = ShopifyClient()
    first = [{"id": value} for value in range(250)]
    second = [{"id": 249}, {"id": 250}]
    client.fetch_products = AsyncMock(
        side_effect=[{"products": first}, {"products": second}]
    )

    products = await client.fetch_all_products("example.com", max_pages=4)

    assert len(products) == 251
    assert products[-1]["id"] == 250
    assert client.fetch_products.await_args_list[0].kwargs == {"limit": 250, "page": 1}
    assert client.fetch_products.await_args_list[1].kwargs == {"limit": 250, "page": 2}


@pytest.mark.asyncio
async def test_repeated_full_page_stops_without_duplicates():
    client = ShopifyClient()
    page = [{"id": value} for value in range(250)]
    client.fetch_products = AsyncMock(side_effect=[{"products": page}, {"products": page}])
    products = await client.fetch_all_products("example.com", max_pages=20)
    assert len(products) == 250
    assert client.fetch_products.await_count == 2


@pytest.mark.asyncio
async def test_max_products_caps_result():
    client = ShopifyClient()
    client.fetch_products = AsyncMock(
        side_effect=[
            {"products": [{"id": value} for value in range(250)]},
            {"products": [{"id": value} for value in range(250, 500)]},
        ]
    )
    products = await client.fetch_all_products(
        "example.com", max_pages=2, max_products=300
    )
    assert len(products) == 300
