import { ApiError, apiFetch } from '../../lib/api';
import type { Credentials, Me } from './types';

/**
 * The signed-in user, or null without a session. Any 4xx means "no session": 401 once B2
 * lands, and 404 until then, when /api/me does not exist yet.
 */
export async function fetchMe(): Promise<Me | null> {
  try {
    return await apiFetch<Me>('/me');
  } catch (error) {
    if (error instanceof ApiError && error.status >= 400 && error.status < 500) return null;
    throw error;
  }
}

export function login(credentials: Credentials): Promise<Me> {
  return apiFetch<Me>('/auth/login', { method: 'POST', body: credentials });
}

export function loginAsGuest(): Promise<Me> {
  return apiFetch<Me>('/auth/guest', { method: 'POST' });
}

export function logout(): Promise<void> {
  return apiFetch<undefined>('/auth/logout', { method: 'POST' });
}
