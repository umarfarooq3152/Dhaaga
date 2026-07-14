"""Product schema — used throughout the API."""

from typing import Optional
from pydantic import BaseModel, Field


class Product(BaseModel):
    """Product data model — matches frontend expectations."""

    id: str = Field(..., description="Composite id: {brand_slug}:{shopify_id}")
    name: str
    description: Optional[str] = None
    price: float
    colors: list[str] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    occasion: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    image: str
    secondaryImage: Optional[str] = None
    product_url: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "limelight:8439992975448",
                "name": "Embroidered Lawn Suit",
                "description": "Beautiful embroidered suit with silk lining",
                "price": 8500.0,
                "colors": ["Blue", "Pink"],
                "sizes": ["S", "M", "L"],
                "occasion": "Eid",
                "tags": ["silk", "embroidery"],
                "image": "https://cdn.shopify.com/...",
                "secondaryImage": "https://cdn.shopify.com/...",
                "product_url": "https://limelight.pk/products/8439992975448",
            }
        }


class ProductSearchResponse(BaseModel):
    """Paginated product search response."""

    items: list[Product]
    total: int
    page: int
    page_size: int
    has_more: bool = Field(
        default=False,
        description="True if more results available on next page",
    )
