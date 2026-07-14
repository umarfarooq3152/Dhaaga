"""Pytest configuration and shared fixtures."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session")
def test_db_url():
    """In-memory SQLite database for tests."""
    return "sqlite:///:memory:"


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return AsyncMock()


@pytest.fixture
def mock_shopify_client():
    """Mock Shopify HTTP client."""
    return AsyncMock()


@pytest.fixture
def fake_settings():
    """Settings for testing."""
    from app.config import Settings

    return Settings(
        database_url="sqlite:///:memory:",
        gemini_api_key="test-key",
        groq_api_key="test-key",
        redis_url="redis://localhost:6379/0",
        frontend_origin="http://localhost:5173",
        environment="test",
        debug=True,
    )


@pytest.fixture
def sample_product():
    """Sample product fixture."""
    from app.schemas.product import Product

    return Product(
        id="limelight:12345",
        name="Embroidered Lawn Suit",
        description="Beautiful embroidered suit with silk lining",
        price=8500.0,
        colors=["Blue", "Pink"],
        sizes=["S", "M", "L", "XL"],
        occasion="Eid",
        tags=["silk", "embroidery"],
        image="https://example.com/image1.jpg",
        secondary_image="https://example.com/image2.jpg",
        product_url="https://limelight.pk/products/12345",
    )
