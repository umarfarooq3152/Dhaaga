from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.routers.extension import search_store
from app.schemas.extension import (
    ExtensionIntent,
    ExtensionProductResult,
    ExtensionSearchMeta,
    ExtensionSearchRequest,
    ExtensionSearchResponse,
)
from app.services.extension_search_service import ExtensionSearchError


@pytest.mark.asyncio
async def test_extension_search_returns_camel_case_contract():
    service = AsyncMock()
    service.search.return_value = ExtensionSearchResponse(
        intent=ExtensionIntent(category="t-shirt", color="black", size="M", priceMax=3000),
        products=[
            ExtensionProductResult(
                id="1",
                title="Core T Shirt",
                price=2800,
                imageUrl="https://cdn.example.com/1.jpg",
                productUrl="https://outfitters.com.pk/products/core-t-shirt",
                score=10,
                reason="Black option, size M, and within your budget.",
            )
        ],
        meta=ExtensionSearchMeta(
            storeDomain="outfitters.com.pk",
            fetchedCount=500,
            catalogCapped=True,
            relaxed=False,
            durationMs=1200,
        ),
    )
    payload = ExtensionSearchRequest(
        query="black t-shirt size M under 3000",
        storeOrigin="https://outfitters.com.pk",
    )

    # SlowAPI wraps the route; call the wrapped endpoint to verify orchestration
    # without involving the project's currently incompatible legacy TestClient.
    result = await search_store.__wrapped__(MagicMock(), payload, service)
    body = result.model_dump(by_alias=True)

    assert body["intent"]["priceMax"] == 3000
    assert body["products"][0]["imageUrl"].startswith("https://")
    assert body["meta"]["catalogCapped"] is True
    service.search.assert_awaited_once_with(payload.query, payload.store_origin, None)


@pytest.mark.asyncio
async def test_extension_search_returns_typed_safe_error():
    service = AsyncMock()
    service.search.side_effect = ExtensionSearchError(
        "UNSUPPORTED_STORE", "Open Outfitters in the active tab to use this MVP."
    )
    payload = ExtensionSearchRequest(query="shirt", storeOrigin="https://evil.example")

    with pytest.raises(HTTPException) as caught:
        await search_store.__wrapped__(MagicMock(), payload, service)

    assert caught.value.status_code == 400
    assert caught.value.detail == {
        "code": "UNSUPPORTED_STORE",
        "message": "Open Outfitters in the active tab to use this MVP.",
    }
