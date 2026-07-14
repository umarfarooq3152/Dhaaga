import { useEffect, useState } from 'react';
import { createDevice } from '../api/devices';
import { getStoredDeviceId, setStoredDeviceId } from '../api/client';

/** Bootstraps an anonymous device id (no signup required) — persisted to
 * localStorage so wishlist/size preferences survive across visits. */
export function useDeviceId(): string | null {
  const [deviceId, setDeviceId] = useState<string | null>(() => getStoredDeviceId());

  useEffect(() => {
    if (deviceId) return;
    let cancelled = false;

    createDevice()
      .then((id) => {
        if (cancelled) return;
        setStoredDeviceId(id);
        setDeviceId(id);
      })
      .catch((error) => {
        console.error('Failed to register device:', error);
      });

    return () => {
      cancelled = true;
    };
  }, [deviceId]);

  return deviceId;
}
