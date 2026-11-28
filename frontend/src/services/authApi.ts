import { config } from '../lib/config';
import {
  AuthResponse,
  DashboardAccessResponse,
  InitializationStatus,
  MessageResponse,
  OnboardingComprehensiveStatus,
  OnboardingProfileRequest,
  OnboardingStatus,
  PrivacyDataSummary,
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

export function getCsrfFromCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|; )\s*pfm_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function isValidCsrfToken(token: string | null): boolean {
  return typeof token === 'string' && token.includes('.') && token.length > 40;
}

export async function fetchCsrfToken(forceRefresh = false): Promise<string> {
  const cookieToken = getCsrfFromCookie();
  if (!forceRefresh && isValidCsrfToken(cookieToken)) {
    cachedCsrfToken = cookieToken;
    return cookieToken!;
  }

  try {
    const url = `${config.apiBaseUrl}/api/v1/auth/csrf${forceRefresh ? '?refresh=true' : ''}`;
    const res = await fetch(url, {
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

export function extractApiErrorMessage(data: unknown, status: number): string {
  if (data && typeof data === 'object') {
    if ('detail' in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail;
      }
      if (Array.isArray(detail) && detail.length > 0) {
        return detail
          .map((item) => {
            if (item && typeof item === 'object' && 'msg' in item) {
              const loc = Array.isArray((item as { loc?: unknown[] }).loc)
                ? (item as { loc: unknown[] }).loc
                    .filter((part) => part !== 'body')
                    .join('.')
                : '';
              const msg = String((item as { msg: unknown }).msg);
              return loc ? `${loc}: ${msg}` : msg;
            }
            return String(item);
          })
          .join('; ');
      }
    }
    if ('message' in data && typeof (data as { message: unknown }).message === 'string') {
      return (data as { message: string }).message;
    }
  }
  return `Request failed with status ${status}`;
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
    let token = cachedCsrfToken || getCsrfFromCookie();
    if (!isValidCsrfToken(token)) {
      token = await fetchCsrfToken(true);
    }
    if (token) {
      headers['X-CSRF-Token'] = token;
    }
  }

  let response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Ensure session cookies are transmitted
  });

  // Auto-recovery: If 403 CSRF error, force refresh CSRF token and retry once
  if (response.status === 403 && ['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
    const cloned = response.clone();
    try {
      const errJson = await cloned.json();
      const detail = String(errJson?.detail || '');
      if (detail.toLowerCase().includes('csrf')) {
        const freshToken = await fetchCsrfToken(true);
        if (freshToken) {
          headers['X-CSRF-Token'] = freshToken;
          response = await fetch(url, {
            ...options,
            headers,
            credentials: 'include',
          });
        }
      }
    } catch {
      // Cloned body read failed
    }
  }

  // Update cached CSRF token if cookie updated
  const freshCookieToken = getCsrfFromCookie();
  if (freshCookieToken && isValidCsrfToken(freshCookieToken)) {
    cachedCsrfToken = freshCookieToken;
  }

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const errorMsg = extractApiErrorMessage(data, response.status);
    if (
      response.status === 401 &&
      !endpoint.includes('/auth/login') &&
      !endpoint.includes('/auth/register') &&
      !endpoint.includes('/auth/me') &&
      typeof window !== 'undefined'
    ) {
      window.dispatchEvent(new CustomEvent('pfm:session-expired', { detail: errorMsg }));
    }
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

  changePassword: (
    currentPassword: string,
    newPassword: string,
    revokeOtherSessions: boolean = true
  ) =>
    authRequest<MessageResponse>('/api/v1/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        revoke_other_sessions: revokeOtherSessions,
      }),
    }),

  getProfile: () => authRequest<User>('/api/v1/users/me'),

  getPrivacySummary: () => authRequest<PrivacyDataSummary>('/api/v1/users/me/privacy-summary'),

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

  getComprehensiveOnboardingStatus: () =>
    authRequest<OnboardingComprehensiveStatus>('/api/v1/onboarding/status'),

  updateOnboarding: (data: Partial<UserPreferences> & { full_name?: string; current_step?: number }) =>
    authRequest<OnboardingStatus>('/api/v1/onboarding', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  saveOnboardingProfile: (data: OnboardingProfileRequest) =>
    authRequest<OnboardingComprehensiveStatus>('/api/v1/onboarding/profile', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  selectFinancialSetupMethod: (setupMethod: string, bankId?: string) =>
    authRequest<OnboardingComprehensiveStatus>('/api/v1/onboarding/financial-setup/select', {
      method: 'POST',
      body: JSON.stringify({ setup_method: setupMethod, bank_id: bankId }),
    }),

  skipFinancialSetup: (completeOnboarding: boolean = false, reason?: string) =>
    authRequest<OnboardingComprehensiveStatus>('/api/v1/onboarding/financial-setup/skip', {
      method: 'POST',
      body: JSON.stringify({ complete_onboarding: completeOnboarding, reason }),
    }),

  initializeWorkspace: (force: boolean = false) =>
    authRequest<InitializationStatus>('/api/v1/onboarding/initialize', {
      method: 'POST',
      body: JSON.stringify({ force }),
    }),

  retryWorkspaceInitialization: () =>
    authRequest<InitializationStatus>('/api/v1/onboarding/initialize/retry', {
      method: 'POST',
    }),

  getInitializationStatus: () =>
    authRequest<InitializationStatus>('/api/v1/onboarding/initialization-status'),

  checkDashboardAccess: () =>
    authRequest<DashboardAccessResponse>('/api/v1/onboarding/dashboard-access'),

  completeOnboarding: () =>
    authRequest<OnboardingStatus>('/api/v1/onboarding/complete', {
      method: 'POST',
    }),

  skipOnboarding: () =>
    authRequest<OnboardingStatus>('/api/v1/onboarding/skip', {
      method: 'POST',
    }),
};
