"""Device schema."""

from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID


class DeviceCreateResponse(BaseModel):
    """Response when creating a new device."""

    device_id: UUID
    created_at: str


class DeviceSizeUpdate(BaseModel):
    """Request to update device size preference."""

    size: str = Field(..., min_length=1, max_length=10)


class DeviceResponse(BaseModel):
    """Device API response."""

    device_id: UUID
    size: Optional[str] = None
    created_at: str
    last_seen_at: str

    class Config:
        from_attributes = True
