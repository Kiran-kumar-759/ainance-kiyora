import { config } from '../lib/config';
import { extractApiErrorMessage } from './authApi';
import {
  AccountAnalyticsDetailResponse,
  AccountAnalyticsListResponse,
  AnalyticsDashboard,
  CashFlowAnalyticsResponse,
  CategoryAnalyticsResponse,
  ExpenseAnalyticsResponse,
  FinancialReportResponse,
  IncomeAnalyticsResponse,
  PeriodComparisonResponse,
  ReportDefinition,
  ReportType,
  TrendAnalyticsResponse,
} from '../types/analytics';

export interface AnalyticsQueryParams {
  period?: string;
  start_date?: string;
  end_date?: string;
  granularity?: string;
  account_id?: string;
  category_id?: string;
  source?: string;
  category_type?: 'expense' | 'income';
  comparison_preset?: string;
  transaction_type?: string;
  report_type?: ReportType;
}

function buildQueryString(params: Record<string, string | undefined | null>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      qs.append(k, v);
    }
  });
  const encoded = qs.toString();
  return encoded ? `?${encoded}` : '';
}

async function analyticsGet<T>(endpoint: string, params: Record<string, string | undefined | null> = {}): Promise<T> {
  const qs = buildQueryString(params);
  const url = `${config.apiBaseUrl}${endpoint}${qs}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'include',
  });

  if (!response.ok) {
    let data: unknown = null;
    try {
      data = await response.json();
    } catch {
      data = await response.text();
    }
    throw new Error(extractApiErrorMessage(data, response.status));
  }

  return (await response.json()) as T;
}

const REPORT_ENDPOINT_MAP: Record<ReportType, string> = {
  monthly_summary: '/api/v1/reports/summary',
  income_report: '/api/v1/reports/income',
  expense_report: '/api/v1/reports/expenses',
  category_spending: '/api/v1/reports/categories',
  account_activity: '/api/v1/reports/accounts',
  cash_flow: '/api/v1/reports/cashflow',
  savings_report: '/api/v1/reports/savings',
  transaction_summary: '/api/v1/reports/transactions',
};

export const analyticsApi = {
  getDashboard: (params: AnalyticsQueryParams = {}): Promise<AnalyticsDashboard> =>
    analyticsGet<AnalyticsDashboard>('/api/v1/analytics/dashboard', {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
    }),

  getIncome: (params: AnalyticsQueryParams = {}): Promise<IncomeAnalyticsResponse> =>
    analyticsGet<IncomeAnalyticsResponse>('/api/v1/analytics/income', {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      granularity: params.granularity,
      account_id: params.account_id,
      source: params.source,
    }),

  getExpenses: (params: AnalyticsQueryParams = {}): Promise<ExpenseAnalyticsResponse> =>
    analyticsGet<ExpenseAnalyticsResponse>('/api/v1/analytics/expenses', {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      granularity: params.granularity,
      account_id: params.account_id,
      source: params.source,
    }),

  getCashFlow: (params: AnalyticsQueryParams = {}): Promise<CashFlowAnalyticsResponse> =>
    analyticsGet<CashFlowAnalyticsResponse>('/api/v1/analytics/cashflow', {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      granularity: params.granularity,
      account_id: params.account_id,
    }),

  getCategories: (params: AnalyticsQueryParams = {}): Promise<CategoryAnalyticsResponse> =>
    analyticsGet<CategoryAnalyticsResponse>('/api/v1/analytics/categories', {
      category_type: params.category_type,
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      account_id: params.account_id,
      source: params.source,
    }),

  getTrends: (params: AnalyticsQueryParams = {}): Promise<TrendAnalyticsResponse> =>
    analyticsGet<TrendAnalyticsResponse>('/api/v1/analytics/trends', {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      granularity: params.granularity,
      account_id: params.account_id,
    }),

  getComparisons: (params: AnalyticsQueryParams = {}): Promise<PeriodComparisonResponse> =>
    analyticsGet<PeriodComparisonResponse>('/api/v1/analytics/comparisons', {
      comparison_preset: params.comparison_preset,
      start_date: params.start_date,
      end_date: params.end_date,
      account_id: params.account_id,
    }),

  getAccounts: (params: AnalyticsQueryParams = {}): Promise<AccountAnalyticsListResponse> =>
    analyticsGet<AccountAnalyticsListResponse>('/api/v1/analytics/accounts', {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
    }),

  getAccountDetail: (
    accountId: string,
    params: AnalyticsQueryParams = {}
  ): Promise<AccountAnalyticsDetailResponse> =>
    analyticsGet<AccountAnalyticsDetailResponse>(`/api/v1/analytics/accounts/${accountId}`, {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      granularity: params.granularity,
    }),

  listReports: (): Promise<{ reports: ReportDefinition[] }> =>
    analyticsGet<{ reports: ReportDefinition[] }>('/api/v1/reports'),

  getReport: (
    reportType: ReportType,
    params: AnalyticsQueryParams = {}
  ): Promise<FinancialReportResponse> =>
    analyticsGet<FinancialReportResponse>(REPORT_ENDPOINT_MAP[reportType], {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      account_id: params.account_id,
      transaction_type: params.transaction_type,
      category_id: params.category_id,
      source: params.source,
    }),

  exportReportCsv: async (
    reportType: ReportType,
    params: AnalyticsQueryParams = {}
  ): Promise<{ filename: string; content: string }> => {
    const qs = buildQueryString({
      report_type: reportType,
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      account_id: params.account_id,
      transaction_type: params.transaction_type,
      category_id: params.category_id,
      source: params.source,
    });
    const url = `${config.apiBaseUrl}/api/v1/reports/export/csv${qs}`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    });
    if (!response.ok) {
      let data: unknown = null;
      try {
        data = await response.json();
      } catch {
        data = await response.text();
      }
      throw new Error(extractApiErrorMessage(data, response.status));
    }
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/i);
    const filename = match ? match[1] : `pfm_${reportType}.csv`;
    const content = await response.text();
    return { filename, content };
  },
};
