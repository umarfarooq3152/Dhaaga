import { api } from './client';

interface DeviceCreateResponse {
  device_id: string;
  created_at: string;
}

export async function createDevice(): Promise<string> {
  const response = await api.post<DeviceCreateResponse>('/devices');
  return response.device_id;
}

export async function updateDeviceSize(deviceId: string, size: string): Promise<void> {
  await api.patch(`/devices/${deviceId}/size`, { size });
}
