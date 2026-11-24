import { config } from '../lib/config';
import { HealthResponse, ReadinessResponse, PlatformInfo } from '../types';

export class ApiError extends Error {
  status?: number;
  data?: unknown;

  constructor(message: string, status?: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...options.headers,
      },
    });

    clearTimeout(timeoutId);

    const isJson = response.headers.get('content-type')?.includes('application/json');
    const data = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      // 503 is returned for degraded readiness, which still has a valid ReadinessResponse payload
      if (response.status === 503 && typeof data === 'object' && data !== null) {
        return data as T;
      }
      throw new ApiError(
        (data && (data as { message?: string; error?: string }).message) ||
          (data && (data as { error?: string }).error) ||
          `Request failed with status ${response.status}`,
        response.status,
        data
      );
    }

    return data as T;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof ApiError) {
      throw err;
    }
    if (err instanceof Error) {
      if (err.name === 'AbortError') {
        throw new ApiError('Request timed out after 8 seconds', 408);
      }
      throw new ApiError(`Network error: ${err.message}`, 0);
    }
    throw new ApiError('An unknown network error occurred', 0);
  }
}

export const apiClient = {
  getHealth: () => request<HealthResponse>('/health'),
  getReadiness: () => request<ReadinessResponse>('/health/ready'),
  getPlatformInfo: () => request<PlatformInfo>('/api/v1/system/info'),
};
