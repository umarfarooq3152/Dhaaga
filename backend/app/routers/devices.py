"""Devices API router — device registration and management."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.repositories.device_repo import DeviceRepository
from app.schemas.device import DeviceCreateResponse, DeviceSizeUpdate, DeviceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceCreateResponse)
async def register_device(
    session: AsyncSession = Depends(get_session),
) -> DeviceCreateResponse:
    """Register a new anonymous device.
    
    Creates a new device session for tracking preferences and wishlist.
    Returns a device_id to use in X-Device-Id header for subsequent requests.
    """
    try:
        repo = DeviceRepository(session)
        device = await repo.get_or_create()
        await session.commit()
        logger.info(f"Registered device {device.device_id}")
        return DeviceCreateResponse(device_id=device.device_id, created_at=device.created_at)
    except Exception as e:
        logger.error(f"Failed to register device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to register device")


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> DeviceResponse:
    """Get device information.
    
    Args:
        device_id: Device UUID
        
    Returns:
        Device with size and last_seen_at timestamp
    """
    try:
        repo = DeviceRepository(session)
        device = await repo.get_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return DeviceResponse.from_orm(device)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get device")


@router.patch("/{device_id}/size", response_model=DeviceResponse)
async def update_device_size(
    device_id: UUID,
    payload: DeviceSizeUpdate,
    session: AsyncSession = Depends(get_session),
) -> DeviceResponse:
    """Update device size preference.
    
    Args:
        device_id: Device UUID
        payload: { size: "M" }
        
    Returns:
        Updated device
    """
    try:
        repo = DeviceRepository(session)
        device = await repo.get_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        await repo.update_size(device_id, payload.size)
        await session.commit()

        logger.info(f"Updated device {device_id} size to {payload.size}")
        return DeviceResponse.from_orm(device)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update device size: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update device size")
