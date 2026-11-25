import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  ImportBatch,
  ImportCenterOverview,
  ImportColumns,
  ImportCommitResponse,
  ImportMappingConfig,
  ImportMappingProfile,
  ImportPreview,
  ImportRow,
  ImportRowListResponse,
  ImportSummary,
} from '../types/imports';

class ImportsApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number = 0, data: unknown = null) {
    super(message);
    this.name = 'ImportsApiError';
    this.status = status;
    this.data = data;
  }
}

async function importRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
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
      // Ignore cloned body error
    }
  }

  if (response.status === 204) {
    return {} as T;
  }

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const errorMsg = extractApiErrorMessage(data, response.status);
    if (response.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('pfm:session-expired', { detail: errorMsg }));
    }
    throw new ImportsApiError(errorMsg, response.status, data);
  }

  return data as T;
}

export const importsApi = {
  async uploadStatement(
    accountId: string,
    file: File,
    onProgress?: (pct: number) => void
  ): Promise<ImportPreview> {
    // Prepare valid CSRF token first
    let token = getCsrfFromCookie();
    if (!isValidCsrfToken(token)) {
      token = await fetchCsrfToken(true);
    }

    const formData = new FormData();
    formData.append('account_id', accountId);
    formData.append('file', file);

    // Use XMLHttpRequest when available in browser to surface real upload progress
    if (typeof XMLHttpRequest !== 'undefined') {
      return new Promise<ImportPreview>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${config.apiBaseUrl}/api/v1/imports/upload`, true);
        xhr.withCredentials = true;
        if (token) {
          xhr.setRequestHeader('X-CSRF-Token', token);
        }

        xhr.upload.onprogress = (evt) => {
          if (evt.lengthComputable && onProgress) {
            onProgress(Math.round((evt.loaded / evt.total) * 100));
          }
        };

        xhr.onload = () => {
          let parsed: unknown = null;
          try {
            parsed = xhr.responseText ? JSON.parse(xhr.responseText) : null;
          } catch {
            parsed = xhr.responseText;
          }
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(parsed as ImportPreview);
          } else {
            const msg = extractApiErrorMessage(parsed, xhr.status);
            if (xhr.status === 401 && typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('pfm:session-expired', { detail: msg }));
            }
            reject(new ImportsApiError(msg, xhr.status, parsed));
          }
        };

        xhr.onerror = () => {
          reject(new ImportsApiError('Network error while uploading statement.', 0));
        };

        xhr.send(formData);
      });
    }

    return importRequest<ImportPreview>('/api/v1/imports/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async listImports(): Promise<ImportCenterOverview> {
    return importRequest<ImportCenterOverview>('/api/v1/imports');
  },

  async listMappingProfiles(fileFormat?: string): Promise<ImportMappingProfile[]> {
    const q = fileFormat ? `?file_format=${encodeURIComponent(fileFormat)}` : '';
    return importRequest<ImportMappingProfile[]>(`/api/v1/imports/profiles${q}`);
  },

  async getImport(importId: string): Promise<ImportBatch> {
    return importRequest<ImportBatch>(`/api/v1/imports/${importId}`);
  },

  async getPreview(
    importId: string,
    params?: { sheet_name?: string; header_row_index?: number }
  ): Promise<ImportPreview> {
    const q = new URLSearchParams();
    if (params?.sheet_name) q.set('sheet_name', params.sheet_name);
    if (params?.header_row_index !== undefined) {
      q.set('header_row_index', String(params.header_row_index));
    }
    const qs = q.toString() ? `?${q.toString()}` : '';
    return importRequest<ImportPreview>(`/api/v1/imports/${importId}/preview${qs}`);
  },

  async deleteImport(importId: string): Promise<{ message: string }> {
    return importRequest<{ message: string }>(`/api/v1/imports/${importId}`, {
      method: 'DELETE',
    });
  },

  async getColumns(
    importId: string,
    params?: { sheet_name?: string; header_row_index?: number }
  ): Promise<ImportColumns> {
    const q = new URLSearchParams();
    if (params?.sheet_name) q.set('sheet_name', params.sheet_name);
    if (params?.header_row_index !== undefined) {
      q.set('header_row_index', String(params.header_row_index));
    }
    const qs = q.toString() ? `?${q.toString()}` : '';
    return importRequest<ImportColumns>(`/api/v1/imports/${importId}/columns${qs}`);
  },

  async saveMapping(importId: string, mapping: ImportMappingConfig): Promise<ImportBatch> {
    return importRequest<ImportBatch>(`/api/v1/imports/${importId}/mapping`, {
      method: 'PUT',
      body: JSON.stringify(mapping),
    });
  },

  async validateImport(importId: string): Promise<ImportBatch> {
    return importRequest<ImportBatch>(`/api/v1/imports/${importId}/validate`, {
      method: 'POST',
    });
  },

  async listRows(
    importId: string,
    params: {
      status_filter?: string;
      duplicate_only?: boolean;
      search?: string;
      sort_by?: string;
      page?: number;
      page_size?: number;
    } = {}
  ): Promise<ImportRowListResponse> {
    const q = new URLSearchParams();
    if (params.status_filter) q.set('status_filter', params.status_filter);
    if (params.duplicate_only) q.set('duplicate_only', 'true');
    if (params.search) q.set('search', params.search);
    if (params.sort_by) q.set('sort_by', params.sort_by);
    if (params.page) q.set('page', String(params.page));
    if (params.page_size) q.set('page_size', String(params.page_size));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return importRequest<ImportRowListResponse>(`/api/v1/imports/${importId}/rows${qs}`);
  },

  async bulkSelectRows(
    importId: string,
    action: 'select_all_valid' | 'deselect_all' | 'set_selection',
    rowIds?: string[],
    isSelected: boolean = true
  ): Promise<ImportBatch> {
    return importRequest<ImportBatch>(`/api/v1/imports/${importId}/rows/bulk-select`, {
      method: 'PATCH',
      body: JSON.stringify({
        action,
        row_ids: rowIds,
        is_selected: isSelected,
      }),
    });
  },

  async updateRow(
    importId: string,
    rowId: string,
    payload: {
      normalized_date?: string;
      normalized_description?: string;
      normalized_merchant?: string | null;
      normalized_notes?: string | null;
      normalized_amount?: string | number;
      normalized_type?: 'income' | 'expense';
      category_id?: string | null;
      clear_category?: boolean;
      is_selected?: boolean;
      exclude?: boolean;
    }
  ): Promise<ImportRow> {
    return importRequest<ImportRow>(`/api/v1/imports/${importId}/rows/${rowId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  async listDuplicates(importId: string): Promise<ImportRowListResponse> {
    return importRequest<ImportRowListResponse>(`/api/v1/imports/${importId}/duplicates`);
  },

  async reviewDuplicate(
    importId: string,
    rowId: string,
    decision: 'import' | 'skip'
  ): Promise<ImportRow> {
    return importRequest<ImportRow>(
      `/api/v1/imports/${importId}/rows/${rowId}/duplicate-review`,
      {
        method: 'PATCH',
        body: JSON.stringify({ decision }),
      }
    );
  },

  async commitImport(importId: string): Promise<ImportCommitResponse> {
    return importRequest<ImportCommitResponse>(`/api/v1/imports/${importId}/commit`, {
      method: 'POST',
    });
  },

  async getSummary(importId: string): Promise<ImportSummary> {
    return importRequest<ImportSummary>(`/api/v1/imports/${importId}/summary`);
  },
};
