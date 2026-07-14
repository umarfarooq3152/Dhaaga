"""Unit tests for product cache service (with mocks)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.product import Product
from app.services.product_cache_service import ProductCacheService


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_client = AsyncMock()
    redis_client._cache = {}  # In-memory cache for testing

    async def mock_set(key, value, ex=None, nx=False):
        if nx and key in redis_client._cache:
            return None
        redis_client._cache[key] = value
        return True

    async def mock_get(key):
        return redis_client._cache.get(key)

    async def mock_close():
        pass

    redis_client.set = mock_set
    redis_client.get = mock_get
    redis_client.close = mock_close
    redis_client.setex = AsyncMock(
        side_effect=lambda key, ttl, value: redis_client._cache.update({key: value})
    )

    return redis_client


@pytest.fixture
async def cache_service(mock_redis):
    """Create cache service with mocked Redis."""
    return ProductCacheService(mock_redis)


class TestProductCacheService:
    """Test product cache service with mocked Redis."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache_service, mock_redis):
        """Test setting and retrieving cached products."""
        brand_slug = "limelight"
        products = [
            Product(
                id=f"limelight:1",
                name="Test Product 1",
                description="A test product",
                price=5000.0,
                colors=["Red"],
                sizes=["M"],
                occasion="casual",
                tags=["cotton"],
                image="https://example.com/img1.jpg",
                secondaryImage=None,
                product_url="https://limelight.pk/products/test1",
            ),
            Product(
                id=f"limelight:2",
                name="Test Product 2",
                description="Another test product",
                price=3000.0,
                colors=["Blue"],
                sizes=["S"],
                occasion="formal",
                tags=["silk"],
                image="https://example.com/img2.jpg",
                secondaryImage=None,
                product_url="https://limelight.pk/products/test2",
            ),
        ]

        # Mock redis.get to return serialized products
        async def mock_get(key):
            if key == "products:limelight":
                products_data = [
                    p.dict() if hasattr(p, "dict") else dict(p) for p in products
                ]
                return json.dumps(products_data)
            return None

        cache_service.redis.get = mock_get

        # Cache products
        result = await cache_service.set_cached_products(
            brand_slug, products, ttl=3600
        )
        assert result is True

        # Retrieve cached products
        cached = await cache_service.get_cached_products(brand_slug)
        assert cached is not None
        assert len(cached) == 2
        assert cached[0].id == "limelight:1"
        assert cached[1].name == "Test Product 2"

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_service):
        """Test cache miss returns None."""
        cache_service.redis.get = AsyncMock(return_value=None)
        cached = await cache_service.get_cached_products("nonexistent_brand")
        assert cached is None

    @pytest.mark.asyncio
    async def test_refresh_lock_acquisition(self, cache_service):
        """Test refresh lock prevents concurrent refreshes."""
        brand_slug = "limelight"
        cache_dict = {}

        async def mock_set(key, value, ex=None, nx=False):
            if nx and key in cache_dict:
                return None
            cache_dict[key] = value
            return True

        cache_service.redis.set = mock_set

        # First lock should succeed
        lock1 = await cache_service._acquire_refresh_lock(brand_slug)
        assert lock1 is True

        # Second lock should fail (already locked)
        lock2 = await cache_service._acquire_refresh_lock(brand_slug)
        assert lock2 is False

    @pytest.mark.asyncio
    async def test_refresh_lock_expiry_simulation(self, cache_service):
        """Test refresh lock expiry simulation."""
        brand_slug = "limelight"
        cache_dict = {}

        async def mock_set_expiring(key, value, ex=None, nx=False):
            if nx and key in cache_dict:
                return None
            cache_dict[key] = value
            # Simulate expiry
            if ex:
                asyncio.create_task(self._expire_key(cache_dict, key, ex))
            return True

        cache_service.redis.set = mock_set_expiring

        # Acquire lock
        lock1 = await cache_service._acquire_refresh_lock(brand_slug)
        assert lock1 is True

        # Try immediately - should fail
        lock2 = await cache_service._acquire_refresh_lock(brand_slug)
        assert lock2 is False

    async def _expire_key(self, cache_dict, key, seconds):
        """Helper to simulate key expiry."""
        await asyncio.sleep(seconds)
        cache_dict.pop(key, None)

    @pytest.mark.asyncio
    async def test_get_or_refresh_cache_hit(self, cache_service):
        """Test get_or_refresh returns cached data if available."""
        brand_slug = "limelight"
        domain = "limelight.pk"

        # Pre-populate cache
        products = [
            Product(
                id=f"limelight:1",
                name="Cached Product",
                description="Already cached",
                price=5000.0,
                colors=["Red"],
                sizes=["M"],
                occasion="casual",
                tags=[],
                image="",
                secondaryImage=None,
                product_url="",
            )
        ]

        # Mock get_cached_products to return pre-populated data
        cache_service.get_cached_products = AsyncMock(return_value=products)

        # Mock Shopify client to ensure it's NOT called
        with patch.object(
            cache_service.shopify_client, "fetch_all_products"
        ) as mock_fetch:
            result = await cache_service.get_or_refresh(brand_slug, domain)

        # Should return cached data without calling Shopify
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "Cached Product"
        # Shopify should not have been called
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_with_self_healing_fallback(self, cache_service):
        """Test refresh falls back to cached data on empty Shopify response."""
        brand_slug = "limelight"
        domain = "limelight.pk"

        # Pre-populate cache
        cached_products = [
            Product(
                id=f"limelight:1",
                name="Fallback Product",
                description="Fallback",
                price=1000.0,
                colors=["Black"],
                sizes=["M"],
                occasion="casual",
                tags=[],
                image="",
                secondaryImage=None,
                product_url="",
            )
        ]

        # Mock get_cached_products to return fallback data
        cache_service.get_cached_products = AsyncMock(return_value=cached_products)

        # Mock Shopify client to return empty products
        with patch.object(
            cache_service.shopify_client, "fetch_all_products", return_value=[]
        ):
            # Mock acquire lock
            cache_service._acquire_refresh_lock = AsyncMock(return_value=True)

            result = await cache_service.refresh_brand_products(brand_slug, domain)

        # Should return cached data as fallback
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "Fallback Product"

    @pytest.mark.asyncio
    async def test_refresh_all_brands(self, cache_service):
        """Test refreshing multiple brands."""
        brands = [
            {"slug": "limelight", "domain": "limelight.pk"},
            {"slug": "alkaram", "domain": "alkaram.pk"},
        ]

        # Mock refresh_brand_products to return product counts
        cache_service.refresh_brand_products = AsyncMock(return_value=[])

        results = await cache_service.refresh_all_brands(brands)

        assert "limelight" in results
        assert "alkaram" in results
        # Should have been called for each brand
        assert cache_service.refresh_brand_products.call_count == 2

