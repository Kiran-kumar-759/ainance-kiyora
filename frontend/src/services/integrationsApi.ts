import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  IntegrationConnectionSummary,
  IntegrationDisconnectResult,
  IntegrationItem,
  IntegrationsOverview,
  IntegrationTestResult,
} from '../types/integrations';

async function integrationRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
    let token = getCsrfFromCookie();
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
    credentials: 'include',
  });

  if (response.status === 403 && ['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
    try {
      const errJson = await response.clone().json();
      if (String(errJson?.detail || '').toLowerCase().includes('csrf')) {
        const fresh = await fetchCsrfToken(true);
        if (fresh) {
          headers['X-CSRF-Token'] = fresh;
          response = await fetch(url, {
            ...options,
            headers,
            credentials: 'include',
          });
        }
      }
    } catch {
      // ignore JSON parse failure
    }
  }

  if (!response.ok) {
    let errData: unknown = null;
    try {
      errData = await response.json();
    } catch {
      errData = await response.text().catch(() => null);
    }
    throw new Error(extractApiErrorMessage(errData, response.status));
  }

  return (await response.json()) as T;
}

export const integrationsApi = {
  getOverview: (): Promise<IntegrationsOverview> =>
    integrationRequest<IntegrationsOverview>('/api/v1/integrations/overview'),

  listProviders: (): Promise<IntegrationItem[]> =>
    integrationRequest<IntegrationItem[]>('/api/v1/integrations/providers'),

  getProvider: (providerId: string): Promise<IntegrationItem> =>
    integrationRequest<IntegrationItem>(`/api/v1/integrations/providers/${providerId}`),

  testProvider: (providerId: string): Promise<IntegrationTestResult> =>
    integrationRequest<IntegrationTestResult>(`/api/v1/integrations/providers/${providerId}/test`, {
      method: 'POST',
    }),

  listConnections: (): Promise<IntegrationConnectionSummary[]> =>
    integrationRequest<IntegrationConnectionSummary[]>('/api/v1/integrations/connections'),

  disconnectConnection: (connectionId: string): Promise<IntegrationDisconnectResult> =>
    integrationRequest<IntegrationDisconnectResult>(
      `/api/v1/integrations/connections/${connectionId}/disconnect`,
      { method: 'POST' }
    ),
};
