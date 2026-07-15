import { api } from './client';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  preferred_size: string | null;
  department: string | null;
}

interface AuthResponse {
  user: AuthUser;
  token: string;
}

export async function signup(email: string, password: string, name: string): Promise<AuthResponse> {
  return api.post<AuthResponse>('/auth/signup', { email, password, name });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return api.post<AuthResponse>('/auth/login', { email, password });
}

export async function getMe(): Promise<AuthUser> {
  return api.get<AuthUser>('/auth/me');
}

export async function updateProfile(
  updates: Partial<Pick<AuthUser, 'name' | 'preferred_size' | 'department'>>
): Promise<AuthUser> {
  return api.patch<AuthUser>('/auth/me', updates);
}
