from typing import Any

import pytest

from app.schemas.product import Product
from app.services.live_product_service import LiveProductValidationService


def product(external_id: str) -> Product:
    return Product(
        id=f"brand:{external_id}",
        name="Cached Lawn Kurta",
        description="Cached description",
        price=9999,
        colors=["Blue"],
        sizes=["S", "M"],
        category="Kurta",
        department="women",
        image="https://cdn.example/image.jpg",
        product_url=f"https://brand.example/products/item-{external_id}",
    )


def payload(external_id: str, *, available: bool = True) -> dict[str, Any]:
    return {
        "id": int(external_id),
        "title": "Live Silk Kurta",
        "description": "<p>Current festive silk description.</p>",
        "type": "Kurta",
        "tags": ["Festive", "Party Wear"],
        "available": available,
        "options": [
            {"name": "Color", "position": 1, "values": ["Green"]},
            {"name": "Size", "position": 2, "values": ["M"]},
        ],
        "variants": [
            {
                "available": available,
                "price": 1250000,
                "options": ["Green", "M"],
            }
        ],
    }


class FakeClient:
    async def fetch_live_product(self, product_url, allowed_domains, session):
        external_id = product_url.rsplit("-", 1)[-1]
        if external_id == "1":
            return "unavailable", None
        return "verified", payload(external_id)


@pytest.mark.asyncio
async def test_live_validation_drops_unavailable_and_updates_current_fields():
    service = LiveProductValidationService(FakeClient(), concurrency=2)

    result = await service.validate(
        [product("1"), product("2")], {"brand.example"}, limit=1
    )

    assert result.unavailable == 1
    assert result.failed == 0
    assert len(result.products) == 1
    current = result.products[0]
    assert current.id == "brand:2"
    assert current.name == "Live Silk Kurta"
    assert current.price == 12500
    assert current.colors == ["Green"]
    assert current.sizes == ["M"]
    assert current.description == "Current festive silk description."
    assert current.live_verified is True
    assert current.live_verified_at is not None
    assert current.semantics is not None
    assert "silk" in current.semantics.fabrics
