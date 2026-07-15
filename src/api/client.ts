const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEVICE_ID_STORAGE_KEY = 'dhaaga_device_id';
const AUTH_TOKEN_STORAGE_KEY = 'dhaaga_auth_token';

export function getStoredDeviceId(): string | null {
  try {
    return localStorage.getItem(DEVICE_ID_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredDeviceId(id: string): void {
  try {
    localStorage.setItem(DEVICE_ID_STORAGE_KEY, id);
  } catch {
    // Ignore storage errors (private browsing, quota, etc.)
  }
}

export function getStoredAuthToken(): string | null {
  try {
    return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredAuthToken(token: string): void {
  try {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  } catch {
    // Ignore storage errors (private browsing, quota, etc.)
  }
}

export function clearStoredAuthToken(): void {
  try {
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    // Ignore storage errors (private browsing, quota, etc.)
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const deviceId = getStoredDeviceId();
  const authToken = getStoredAuthToken();
  // FormData needs the browser to set its own multipart Content-Type
  // (with boundary) — forcing application/json here would break the upload.
  const isFormData = options.body instanceof FormData;
  const headers: HeadersInit = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(deviceId ? { 'X-Device-Id': deviceId } : {}),
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || body.error?.message || detail;
    } catch {
      // Response body wasn't JSON — keep the statusText fallback.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
  postFormData: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', body: formData }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
