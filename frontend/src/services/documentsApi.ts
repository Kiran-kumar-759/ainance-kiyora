import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  DocumentListResponse,
  DocumentOverview,
  DocumentProcessingJob,
  EmailCandidate,
  EmailConnection,
  EmailSyncHistoryItem,
  FinancialDocumentDetail,
  SmsIngestionStatus,
} from '../types/documents';

async function docRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
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

export const documentsApi = {
  getOverview: (): Promise<DocumentOverview> =>
    docRequest<DocumentOverview>('/api/v1/documents/overview'),

  listDocuments: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, String(v));
    });
    const q = qs.toString();
    return docRequest<DocumentListResponse>(`/api/v1/documents${q ? `?${q}` : ''}`);
  },

  getDocument: (id: string): Promise<FinancialDocumentDetail> =>
    docRequest<FinancialDocumentDetail>(`/api/v1/documents/${id}`),

  uploadDocument: async (
    file: File,
    category: string = 'other',
    autoProcess: boolean = true
  ): Promise<FinancialDocumentDetail> => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('document_category', category);
    fd.append('auto_process', String(autoProcess));
    return docRequest<FinancialDocumentDetail>('/api/v1/documents/upload', {
      method: 'POST',
      body: fd,
    });
  },

  deleteDocument: (id: string): Promise<void> =>
    docRequest<void>(`/api/v1/documents/${id}`, { method: 'DELETE' }),

  processDocument: (id: string): Promise<DocumentProcessingJob> =>
    docRequest<DocumentProcessingJob>(`/api/v1/documents/${id}/process`, { method: 'POST' }),

  listProcessingHistory: (): Promise<{ items: DocumentProcessingJob[]; total: number }> =>
    docRequest('/api/v1/documents/processing-history'),

  updateExtraction: (
    id: string,
    payload: Record<string, unknown>
  ): Promise<FinancialDocumentDetail> =>
    docRequest<FinancialDocumentDetail>(`/api/v1/documents/${id}/extraction`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  confirmDocument: (
    id: string,
    payload: Record<string, unknown>
  ): Promise<FinancialDocumentDetail> =>
    docRequest<FinancialDocumentDetail>(`/api/v1/documents/${id}/confirm`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  rejectDocument: (id: string, reason: string): Promise<FinancialDocumentDetail> =>
    docRequest<FinancialDocumentDetail>(`/api/v1/documents/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  linkDocument: (
    id: string,
    target_type: 'bill' | 'transaction' | 'subscription' | 'loan',
    target_id: string
  ): Promise<FinancialDocumentDetail> =>
    docRequest<FinancialDocumentDetail>(`/api/v1/documents/${id}/link`, {
      method: 'POST',
      body: JSON.stringify({ target_type, target_id }),
    }),

  fetchPreviewBlob: async (
    id: string,
    page: number = 1
  ): Promise<{ blob: Blob; totalPages: number }> => {
    const res = await fetch(`${config.apiBaseUrl}/api/v1/documents/${id}/preview?page=${page}`, {
      credentials: 'include',
    });
    if (!res.ok) throw new Error('Unable to load document preview.');
    const totalPages = Number(res.headers.get('X-Total-Pages') || '1') || 1;
    return { blob: await res.blob(), totalPages };
  },

  fetchDownloadBlob: async (id: string): Promise<Blob> => {
    const res = await fetch(`${config.apiBaseUrl}/api/v1/documents/${id}/download`, {
      credentials: 'include',
    });
    if (!res.ok) throw new Error('Unable to download private document.');
    return res.blob();
  },
};

export const emailIngestionApi = {
  getConnections: (): Promise<EmailConnection[]> =>
    docRequest<EmailConnection[]>('/api/v1/email/connections'),

  getGmailConnectUrl: (): Promise<{ authorization_url: string; state: string; scopes: string[] }> =>
    docRequest('/api/v1/email/gmail/connect'),

  disconnectGmail: (): Promise<EmailConnection> =>
    docRequest<EmailConnection>('/api/v1/email/gmail/disconnect', { method: 'POST' }),

  syncGmail: (payload: Record<string, unknown> = {}): Promise<EmailSyncHistoryItem> =>
    docRequest<EmailSyncHistoryItem>('/api/v1/email/gmail/sync', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listSyncHistory: (): Promise<EmailSyncHistoryItem[]> =>
    docRequest<EmailSyncHistoryItem[]>('/api/v1/email/sync-history'),

  listCandidates: (statusFilter?: string): Promise<EmailCandidate[]> => {
    const q = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
    return docRequest<EmailCandidate[]>(`/api/v1/email/candidates${q}`);
  },

  confirmCandidate: (
    candidateId: string,
    payload: Record<string, unknown>
  ): Promise<EmailCandidate> =>
    docRequest<EmailCandidate>(`/api/v1/email/candidates/${candidateId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  rejectCandidate: (candidateId: string, reason: string): Promise<EmailCandidate> =>
    docRequest<EmailCandidate>(`/api/v1/email/candidates/${candidateId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  getSmsStatus: (): Promise<SmsIngestionStatus> =>
    docRequest<SmsIngestionStatus>('/api/v1/email/sms/status'),
};
