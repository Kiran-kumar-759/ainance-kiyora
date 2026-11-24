import { config } from '../lib/config';
import {
  AuthResponse,
  MessageResponse,
  OnboardingStatus,
  User,
  UserPreferences,
  UserSession,
} from '../types/auth';

class AuthApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number = 0, data: unknown = null) {
    super(message);
    this.name = 'AuthApiError';
    this.status = status;
    this.data = data;
  }
}

// In-memory CSRF token cache
let cachedCsrfToken: string | null = null;

function getCsrfFromCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|; )\s*pfm_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function fetchCsrfToken(): Promise<string> {
  const cookieToken = getCsrfFromCookie();
  if (cookieToken) {
    cachedCsrfToken = cookieToken;
    return cookieToken;
  }

  try {
    const res = await fetch(`${config.apiBaseUrl}/api/v1/auth/csrf`, {
      method: 'GET',
      credentials: 'include',
    });
    if (res.ok) {
      const data = await res.json();
      cachedCsrfToken = data.csrf_token;
      return data.csrf_token;
    }
  } catch {
    // Pass through
  }
  return '';
}

async function authRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(options.headers as Record<string, string>),
  };

  // Add CSRF token for mutating requests
  if (['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
    const token = cachedCsrfToken || getCsrfFromCookie() || (await fetchCsrfToken());
    if (token) {
      headers['X-CSRF-Token'] = token;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Ensure session cookies are transmitted
  });

  // Update cached CSRF token if cookie updated
  const freshCookieToken = getCsrfFromCookie();
  if (freshCookieToken) {
    cachedCsrfToken = freshCookieToken;
  }

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const errorMsg =
      (data && typeof data === 'object' && 'detail' in data && (data as { detail: string }).detail) ||
      (data && typeof data === 'object' && 'message' in data && (data as { message: string }).message) ||
      `Request failed with status ${response.status}`;
    throw new AuthApiError(errorMsg, response.status, data);
  }

  return data as T;
}

export const authApi = {
  getCsrf: fetchCsrfToken,

  register: (fullName: string, email: string, password: string) =>
    authRequest<AuthResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ full_name: fullName, email, password }),
    }),

  login: (email: string, password: string) =>
    authRequest<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  getMe: () => authRequest<User>('/api/v1/auth/me'),

  logout: () =>
    authRequest<MessageResponse>('/api/v1/auth/logout', {
      method: 'POST',
    }),

  logoutAll: () =>
    authRequest<MessageResponse>('/api/v1/auth/logout-all', {
      method: 'POST',
    }),

  listSessions: () => authRequest<UserSession[]>('/api/v1/auth/sessions'),

  revokeSession: (sessionId: string) =>
    authRequest<MessageResponse>(`/api/v1/auth/sessions/${sessionId}`, {
      method: 'DELETE',
    }),

  verifyEmail: (token: string) =>
    authRequest<AuthResponse>('/api/v1/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),

  resendVerification: (email: string) =>
    authRequest<MessageResponse>('/api/v1/auth/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  forgotPassword: (email: string) =>
    authRequest<MessageResponse>('/api/v1/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, newPassword: string) =>
    authRequest<MessageResponse>('/api/v1/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  getProfile: () => authRequest<User>('/api/v1/users/me'),

  updateProfile: (fullName: string) =>
    authRequest<User>('/api/v1/users/me', {
      method: 'PATCH',
      body: JSON.stringify({ full_name: fullName }),
    }),

  getPreferences: () => authRequest<UserPreferences>('/api/v1/users/me/preferences'),

  updatePreferences: (preferences: Partial<UserPreferences>) =>
    authRequest<UserPreferences>('/api/v1/users/me/preferences', {
      method: 'PATCH',
      body: JSON.stringify(preferences),
    }),

  getOnboarding: () => authRequest<OnboardingStatus>('/api/v1/onboarding'),

  updateOnboarding: (data: Partial<UserPreferences> & { full_name?: string }) =>
    authRequest<OnboardingStatus>('/api/v1/onboarding', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  completeOnboarding: () =>
    authRequest<OnboardingStatus>('/api/v1/onboarding/complete', {
      method: 'POST',
    }),

  skipOnboarding: () =>
    authRequest<OnboardingStatus>('/api/v1/onboarding/skip', {
      method: 'POST',
    }),
};
