import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  EmiCalculatorResult,
  Loan,
  LoanAnalytics,
  LoanListResponse,
  LoanOverview,
  LoanPayment,
  LoanPrepaymentScenario,
  Subscription,
  SubscriptionAnalytics,
  SubscriptionCandidate,
  SubscriptionListResponse,
  SubscriptionOverview,
  SubscriptionPayment,
} from '../types/phase6';

async function phase6Request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();

  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
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

  let response = await fetch(url, { ...options, headers, credentials: 'include' });

  if (response.status === 403 && ['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
    try {
      const errJson = await response.clone().json();
      if (String(errJson?.detail || '').toLowerCase().includes('csrf')) {
        const fresh = await fetchCsrfToken(true);
        if (fresh) {
          headers['X-CSRF-Token'] = fresh;
          response = await fetch(url, { ...options, headers, credentials: 'include' });
        }
      }
    } catch {
      // ignore
    }
  }

  if (!response.ok) {
    let data: unknown = null;
    try {
      data = await response.json();
    } catch {
      data = await response.text();
    }
    throw new Error(extractApiErrorMessage(data, response.status));
  }

  if (response.status === 204) return {} as T;
  return (await response.json()) as T;
}

export const subscriptionsApi = {
  getOverview: (): Promise<SubscriptionOverview> =>
    phase6Request<SubscriptionOverview>('/api/v1/subscriptions/overview'),

  getAnalytics: (): Promise<SubscriptionAnalytics> =>
    phase6Request<SubscriptionAnalytics>('/api/v1/subscriptions/analytics'),

  listSubscriptions: (params: Record<string, string | number | boolean | undefined> = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, String(v));
    });
    const s = qs.toString();
    return phase6Request<SubscriptionListResponse>(`/api/v1/subscriptions${s ? `?${s}` : ''}`);
  },

  getSubscription: (id: string): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}`),

  createSubscription: (payload: Record<string, unknown>): Promise<Subscription> =>
    phase6Request<Subscription>('/api/v1/subscriptions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateSubscription: (id: string, payload: Record<string, unknown>): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  changePrice: (id: string, payload: Record<string, unknown>): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}/price-change`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  pauseSubscription: (id: string): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}/pause`, { method: 'POST' }),

  resumeSubscription: (id: string): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}/resume`, { method: 'POST' }),

  cancelSubscription: (id: string, payload: Record<string, unknown> = {}): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  archiveSubscription: (id: string): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}/archive`, { method: 'POST' }),

  recordPayment: (id: string, payload: Record<string, unknown>): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}/payments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  linkTransaction: (id: string, payload: Record<string, unknown>): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${id}/payments/link-transaction`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  reversePayment: (subId: string, paymentId: string, reason: string): Promise<Subscription> =>
    phase6Request<Subscription>(`/api/v1/subscriptions/${subId}/payments/${paymentId}/reverse`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  listPayments: (): Promise<{ items: SubscriptionPayment[]; total: number }> =>
    phase6Request('/api/v1/subscriptions/payments'),

  listCandidates: (): Promise<SubscriptionCandidate[]> =>
    phase6Request<SubscriptionCandidate[]>('/api/v1/subscriptions/candidates'),

  decideCandidate: (
    merchant_key: string,
    action: 'ignore' | 'link',
    subscription_id?: string
  ): Promise<{ status: string }> =>
    phase6Request('/api/v1/subscriptions/candidates/decision', {
      method: 'POST',
      body: JSON.stringify({ merchant_key, action, subscription_id }),
    }),
};

export const loansApi = {
  calculateEmi: (payload: Record<string, unknown>): Promise<EmiCalculatorResult> =>
    phase6Request<EmiCalculatorResult>('/api/v1/loans/calculator', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getOverview: (): Promise<LoanOverview> => phase6Request<LoanOverview>('/api/v1/loans/overview'),

  getAnalytics: (): Promise<LoanAnalytics> => phase6Request<LoanAnalytics>('/api/v1/loans/analytics'),

  listLoans: (params: Record<string, string | number | boolean | undefined> = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, String(v));
    });
    const s = qs.toString();
    return phase6Request<LoanListResponse>(`/api/v1/loans${s ? `?${s}` : ''}`);
  },

  getLoan: (id: string): Promise<Loan> => phase6Request<Loan>(`/api/v1/loans/${id}`),

  createLoan: (payload: Record<string, unknown>): Promise<Loan> =>
    phase6Request<Loan>('/api/v1/loans', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateLoan: (id: string, payload: Record<string, unknown>): Promise<Loan> =>
    phase6Request<Loan>(`/api/v1/loans/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  archiveLoan: (id: string): Promise<Loan> =>
    phase6Request<Loan>(`/api/v1/loans/${id}/archive`, { method: 'POST' }),

  reviseRate: (id: string, payload: Record<string, unknown>): Promise<Loan> =>
    phase6Request<Loan>(`/api/v1/loans/${id}/rate-revision`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  simulatePrepayment: (id: string, payload: Record<string, unknown>): Promise<LoanPrepaymentScenario> =>
    phase6Request<LoanPrepaymentScenario>(`/api/v1/loans/${id}/prepayment-scenario`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  recordPayment: (id: string, payload: Record<string, unknown>): Promise<Loan> =>
    phase6Request<Loan>(`/api/v1/loans/${id}/payments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  linkTransaction: (id: string, payload: Record<string, unknown>): Promise<Loan> =>
    phase6Request<Loan>(`/api/v1/loans/${id}/payments/link-transaction`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  reversePayment: (loanId: string, paymentId: string, reason: string): Promise<Loan> =>
    phase6Request<Loan>(`/api/v1/loans/${loanId}/payments/${paymentId}/reverse`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  listPayments: (): Promise<{ items: LoanPayment[]; total: number }> =>
    phase6Request('/api/v1/loans/payments'),
};
