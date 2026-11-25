import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  Bill,
  BillDocument,
  BillListResponse,
  BillPayment,
  BillsOverview,
  NotificationListResponse,
  ProcessRemindersResult,
  RecurrenceSchedule,
} from '../types/bills';

async function billsRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();
  const isFormData = options.body instanceof FormData;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
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

export const billsApi = {
  getOverview: (): Promise<BillsOverview> => billsRequest<BillsOverview>('/api/v1/bills/overview'),

  listBills: (params: {
    status_filter?: string;
    bill_category?: string;
    bill_type?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
    sort_by?: string;
    include_archived?: boolean;
    page?: number;
    page_size?: number;
  } = {}): Promise<BillListResponse> => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        qs.append(k, String(v));
      }
    });
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return billsRequest<BillListResponse>(`/api/v1/bills${suffix}`);
  },

  getBill: (billId: string): Promise<Bill> => billsRequest<Bill>(`/api/v1/bills/${billId}`),

  createBill: (payload: Record<string, unknown>): Promise<Bill> =>
    billsRequest<Bill>('/api/v1/bills', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateBill: (billId: string, payload: Record<string, unknown>): Promise<Bill> =>
    billsRequest<Bill>(`/api/v1/bills/${billId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  archiveBill: (billId: string): Promise<Bill> =>
    billsRequest<Bill>(`/api/v1/bills/${billId}/archive`, { method: 'POST' }),

  recordPayment: (
    billId: string,
    payload: {
      amount_paid: string;
      payment_date: string;
      financial_account_id: string;
      payment_method: string;
      reference_number?: string;
      notes?: string;
      idempotency_key?: string;
      mark_as_fully_paid?: boolean;
    }
  ): Promise<Bill> =>
    billsRequest<Bill>(`/api/v1/bills/${billId}/payments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  linkTransaction: (
    billId: string,
    payload: {
      transaction_id: string;
      payment_method: string;
      notes?: string;
      mark_as_fully_paid?: boolean;
    }
  ): Promise<Bill> =>
    billsRequest<Bill>(`/api/v1/bills/${billId}/payments/link-transaction`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listPayments: (billId?: string): Promise<{ items: BillPayment[]; total: number }> =>
    billsRequest<{ items: BillPayment[]; total: number }>(
      billId ? `/api/v1/bills/${billId}/payments` : '/api/v1/bills/payments'
    ),

  listSchedules: (): Promise<RecurrenceSchedule[]> =>
    billsRequest<RecurrenceSchedule[]>('/api/v1/bills/schedules'),

  updateSchedule: (scheduleId: string, payload: Record<string, unknown>): Promise<RecurrenceSchedule> =>
    billsRequest<RecurrenceSchedule>(`/api/v1/bills/schedules/${scheduleId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  generateNextOccurrence: (
    scheduleId: string
  ): Promise<{ created: boolean; message: string; occurrence?: Bill | null }> =>
    billsRequest<{ created: boolean; message: string; occurrence?: Bill | null }>(
      `/api/v1/bills/schedules/${scheduleId}/generate-next`,
      { method: 'POST' }
    ),

  updateReminders: (
    billId: string,
    payload: {
      reminder_enabled?: boolean;
      reminder_days_before?: number[];
      notification_channels?: { in_app: boolean; email: boolean; sms: boolean };
    }
  ): Promise<Bill> =>
    billsRequest<Bill>(`/api/v1/bills/${billId}/reminders`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  processReminders: (): Promise<ProcessRemindersResult> =>
    billsRequest<ProcessRemindersResult>('/api/v1/bills/reminders/process', {
      method: 'POST',
    }),

  uploadDocument: (billId: string, file: File): Promise<BillDocument> => {
    const fd = new FormData();
    fd.append('file', file);
    return billsRequest<BillDocument>(`/api/v1/bills/${billId}/documents`, {
      method: 'POST',
      body: fd,
    });
  },

  downloadDocument: async (billId: string, docId: string, filename: string): Promise<void> => {
    const url = `${config.apiBaseUrl}/api/v1/bills/${billId}/documents/${docId}/download`;
    const res = await fetch(url, { credentials: 'include' });
    if (!res.ok) {
      throw new Error(`Download failed (${res.status})`);
    }
    const blob = await res.blob();
    const objUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objUrl);
  },

  listNotifications: (unreadOnly: boolean = false): Promise<NotificationListResponse> =>
    billsRequest<NotificationListResponse>(
      `/api/v1/notifications${unreadOnly ? '?unread_only=true' : ''}`
    ),

  getUnreadCount: (): Promise<{ unread_count: number }> =>
    billsRequest<{ unread_count: number }>('/api/v1/notifications/unread-count'),

  markNotificationRead: (notificationId: string): Promise<{ id: string; is_read: boolean }> =>
    billsRequest(`/api/v1/notifications/${notificationId}/read`, { method: 'PATCH' }),

  markAllNotificationsRead: (): Promise<{ marked_read: number }> =>
    billsRequest('/api/v1/notifications/read-all', { method: 'POST' }),
};
