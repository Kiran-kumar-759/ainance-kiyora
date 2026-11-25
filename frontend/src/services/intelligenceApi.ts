import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  AiModelMetadata,
  AiProcessingJob,
  CategorizationFeedbackItem,
  FinancialInsight,
  FinancialInsightList,
  IntelligenceOverview,
  MerchantIdentityItem,
  MerchantList,
  RecurringCandidateList,
  RecurringPaymentCandidate,
  SpendingAnomaly,
  SpendingAnomalyList,
  SpendingPatterns,
  TransactionCategorization,
  TransactionCategorizationList,
} from '../types/intelligence';

async function intelRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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
    if (token) headers['X-CSRF-Token'] = token;
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

export const intelligenceApi = {
  getOverview(lookbackDays = 180): Promise<IntelligenceOverview> {
    return intelRequest<IntelligenceOverview>(
      `/api/v1/intelligence/overview?lookback_days=${lookbackDays}`
    );
  },

  runFullPipeline(payload: {
    reanalyze_all?: boolean;
    use_ai_fallback?: boolean;
    train_model?: boolean;
    lookback_days?: number;
    async_job?: boolean;
  } = {}): Promise<AiProcessingJob> {
    return intelRequest<AiProcessingJob>('/api/v1/intelligence/run', {
      method: 'POST',
      body: JSON.stringify({
        reanalyze_all: false,
        use_ai_fallback: true,
        train_model: true,
        lookback_days: 365,
        async_job: false,
        ...payload,
      }),
    });
  },

  trainMlModel(): Promise<AiModelMetadata> {
    return intelRequest<AiModelMetadata>('/api/v1/intelligence/ml/train', {
      method: 'POST',
      body: JSON.stringify({}),
    });
  },

  listCategorizations(params: {
    review_status?: string;
    method?: string;
    search?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<TransactionCategorizationList> {
    const qs = new URLSearchParams();
    if (params.review_status) qs.set('review_status', params.review_status);
    if (params.method) qs.set('method', params.method);
    if (params.search) qs.set('search', params.search);
    if (params.page) qs.set('page', String(params.page));
    if (params.page_size) qs.set('page_size', String(params.page_size));
    const qStr = qs.toString();
    return intelRequest<TransactionCategorizationList>(
      `/api/v1/intelligence/categorizations${qStr ? `?${qStr}` : ''}`
    );
  },

  overrideCategorization(
    transactionId: string,
    payload: {
      category_id: string;
      normalized_merchant_name?: string;
      save_merchant_mapping?: boolean;
      action?: 'confirm' | 'override' | 'dismiss';
      notes?: string;
    }
  ): Promise<TransactionCategorization> {
    return intelRequest<TransactionCategorization>(
      `/api/v1/intelligence/categorizations/${transactionId}/override`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  },

  listFeedback(): Promise<CategorizationFeedbackItem[]> {
    return intelRequest<CategorizationFeedbackItem[]>('/api/v1/intelligence/feedback');
  },

  listMerchants(
    params: { search?: string; page?: number; page_size?: number } = {}
  ): Promise<MerchantList> {
    const qs = new URLSearchParams();
    if (params.search) qs.set('search', params.search);
    if (params.page) qs.set('page', String(params.page));
    if (params.page_size) qs.set('page_size', String(params.page_size));
    const qStr = qs.toString();
    return intelRequest<MerchantList>(`/api/v1/intelligence/merchants${qStr ? `?${qStr}` : ''}`);
  },

  updateMerchant(
    merchantId: string,
    payload: {
      normalized_name?: string;
      default_category_id?: string;
      is_user_confirmed?: boolean;
      apply_to_existing_transactions?: boolean;
    }
  ): Promise<MerchantIdentityItem> {
    return intelRequest<MerchantIdentityItem>(`/api/v1/intelligence/merchants/${merchantId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  listRecurringCandidates(reviewStatus?: string): Promise<RecurringCandidateList> {
    const qs = reviewStatus ? `?review_status=${encodeURIComponent(reviewStatus)}` : '';
    return intelRequest<RecurringCandidateList>(
      `/api/v1/intelligence/recurring-candidates${qs}`
    );
  },

  decideRecurringCandidate(
    candidateId: string,
    payload: {
      decision: 'confirm' | 'reject' | 'link_subscription';
      create_subscription?: boolean;
      subscription_id?: string;
    }
  ): Promise<RecurringPaymentCandidate> {
    return intelRequest<RecurringPaymentCandidate>(
      `/api/v1/intelligence/recurring-candidates/${candidateId}/decision`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  },

  getSpendingPatterns(params: { date_from?: string; date_to?: string } = {}): Promise<SpendingPatterns> {
    const qs = new URLSearchParams();
    if (params.date_from) qs.set('date_from', params.date_from);
    if (params.date_to) qs.set('date_to', params.date_to);
    const qStr = qs.toString();
    return intelRequest<SpendingPatterns>(
      `/api/v1/intelligence/patterns${qStr ? `?${qStr}` : ''}`
    );
  },

  listAnomalies(params: { review_status?: string; severity?: string } = {}): Promise<SpendingAnomalyList> {
    const qs = new URLSearchParams();
    if (params.review_status) qs.set('review_status', params.review_status);
    if (params.severity) qs.set('severity', params.severity);
    const qStr = qs.toString();
    return intelRequest<SpendingAnomalyList>(
      `/api/v1/intelligence/anomalies${qStr ? `?${qStr}` : ''}`
    );
  },

  reviewAnomaly(
    anomalyId: string,
    action: 'acknowledge' | 'dismiss' | 'reopen'
  ): Promise<SpendingAnomaly> {
    return intelRequest<SpendingAnomaly>(`/api/v1/intelligence/anomalies/${anomalyId}/review`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    });
  },

  listInsights(statusFilter?: string): Promise<FinancialInsightList> {
    const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
    return intelRequest<FinancialInsightList>(`/api/v1/intelligence/insights${qs}`);
  },

  reviewInsight(
    insightId: string,
    action: 'mark_read' | 'dismiss' | 'reopen'
  ): Promise<FinancialInsight> {
    return intelRequest<FinancialInsight>(`/api/v1/intelligence/insights/${insightId}/review`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    });
  },
};
