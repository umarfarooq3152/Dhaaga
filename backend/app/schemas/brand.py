"""Brand schema."""

from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID


class BrandResponse(BaseModel):
    """Brand API response."""

    id: UUID
    name: str
    slug: str
    domain: str
    logo_url: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
