import { useCallback, useEffect, useState } from 'react';
import { AuthUser, getMe, login as apiLogin, signup as apiSignup } from '../api/auth';
import { getStoredAuthToken, setStoredAuthToken, clearStoredAuthToken } from '../api/client';

interface UseAuthResult {
  user: AuthUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

/** Manages the logged-in shopper's session — a JWT in localStorage,
 * mirroring the anonymous device-id pattern in useDeviceId. Logging in
 * or signing up folds the current device's anonymous wishlist into the
 * account server-side (see /auth/login, /auth/signup). */
export function useAuth(): UseAuthResult {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!getStoredAuthToken()) {
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    getMe()
      .then((fetchedUser) => {
        if (!cancelled) setUser(fetchedUser);
      })
      .catch(() => {
        // Expired/invalid token — treat as logged out.
        clearStoredAuthToken();
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password);
    setStoredAuthToken(response.token);
    setUser(response.user);
  }, []);

  const signup = useCallback(async (email: string, password: string, name: string) => {
    const response = await apiSignup(email, password, name);
    setStoredAuthToken(response.token);
    setUser(response.user);
  }, []);

  const logout = useCallback(() => {
    clearStoredAuthToken();
    setUser(null);
  }, []);

  return { user, isLoading, login, signup, logout };
}
