"""Device repository — data access for devices."""

from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.device import Device


class DeviceRepository:
    """Repository for devices table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, device_id: Optional[UUID] = None) -> Device:
        """Get device by ID or create a new one."""
        if device_id:
            device = await self.session.get(Device, device_id)
            if device:
                return device

        device = Device()
        self.session.add(device)
        await self.session.flush()
        return device

    async def get_by_id(self, device_id: UUID) -> Optional[Device]:
        """Get device by ID."""
        return await self.session.get(Device, device_id)

    async def update_size(self, device_id: UUID, size: str) -> None:
        """Update device size preference."""
        device = await self.get_by_id(device_id)
        if device:
            device.size = size
            device.last_seen_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def update_last_seen(self, device_id: UUID) -> None:
        """Update device last_seen_at timestamp."""
        device = await self.get_by_id(device_id)
        if device:
            device.last_seen_at = datetime.now(timezone.utc)
            await self.session.flush()
