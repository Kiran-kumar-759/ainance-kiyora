import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  ForecastEvaluation,
  ForecastingOverview,
  ForecastScenario,
} from '../types/forecasting';

async function forecastRequest<T>(
  endpoint: string,
  options: RequestInit & { timeoutMs?: number } = {}
): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();
  const { timeoutMs = 25000, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string>),
  };

  if (['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
    let token = getCsrfFromCookie();
    if (!isValidCsrfToken(token)) {
      token = await fetchCsrfToken(true);
    }
    if (token) headers['X-CSRF-Token'] = token;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: 'include',
      signal: controller.signal,
    });

    if (response.status === 403 && ['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
      try {
        const errJson = await response.clone().json();
        if (String(errJson?.detail || '').toLowerCase().includes('csrf')) {
          const fresh = await fetchCsrfToken(true);
          if (fresh) {
            headers['X-CSRF-Token'] = fresh;
            response = await fetch(url, {
              ...fetchOptions,
              headers,
              credentials: 'include',
              signal: controller.signal,
            });
          }
        }
      } catch {
        // ignore
      }
    }
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') {
      throw new Error('Forecasting request timed out. Please retry.');
    }
    throw err;
  } finally {
    clearTimeout(timer);
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

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const forecastingApi = {
  getOverview(horizonDays = 30, lowBalanceThreshold = 5000): Promise<ForecastingOverview> {
    return forecastRequest<ForecastingOverview>(
      `/api/v1/forecasting/overview?horizon_days=${horizonDays}&low_balance_threshold=${lowBalanceThreshold}`
    );
  },

  generateForecast(payload: {
    horizon_days: number;
    force_refresh?: boolean;
    low_balance_threshold?: number;
  }): Promise<ForecastingOverview> {
    return forecastRequest<ForecastingOverview>('/api/v1/forecasting/generate', {
      method: 'POST',
      body: JSON.stringify({
        force_refresh: true,
        async_job: false,
        low_balance_threshold: 5000,
        ...payload,
      }),
    });
  },

  runScenario(payload: {
    name: string;
    horizon_days: number;
    income_delta_pct: number;
    expense_delta_pct: number;
    extra_recurring_monthly_expense: number;
    extra_loan_payment_monthly: number;
    cancelled_subscription_ids: string[];
    category_adjustments_pct: Record<string, number>;
    save_scenario: boolean;
  }): Promise<ForecastScenario> {
    return forecastRequest<ForecastScenario>('/api/v1/forecasting/scenarios', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  listScenarios(): Promise<ForecastScenario[]> {
    return forecastRequest<ForecastScenario[]>('/api/v1/forecasting/scenarios');
  },

  deleteScenario(id: string): Promise<void> {
    return forecastRequest<void>(`/api/v1/forecasting/scenarios/${id}`, {
      method: 'DELETE',
    });
  },

  runAccuracyBacktest(horizonDays = 30): Promise<ForecastEvaluation> {
    return forecastRequest<ForecastEvaluation>(
      `/api/v1/forecasting/accuracy?horizon_days=${horizonDays}`
    );
  },

  listEvaluations(): Promise<ForecastEvaluation[]> {
    return forecastRequest<ForecastEvaluation[]>('/api/v1/forecasting/evaluation/history');
  },
};
