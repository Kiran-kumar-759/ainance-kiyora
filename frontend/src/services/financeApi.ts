import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  AccountSummary,
  BankInstitutionCatalog,
  BankingConnection,
  BankingProviderInfo,
  BankingSyncResponse,
  BankingSyncRun,
  DiscoveredAccount,
  FinancialAccount,
  FinancialCategory,
  FinancialDashboard,
  FinancialTransaction,
  FinancialTransfer,
  TransactionListResponse,
} from '../types/finance';

class FinanceApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number = 0, data: unknown = null) {
    super(message);
    this.name = 'FinanceApiError';
    this.status = status;
    this.data = data;
  }
}

async function financeRequest<T>(
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

  // Attach CSRF token for mutating requests
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
    throw new FinanceApiError(errorMsg, response.status, data);
  }

  return data as T;
}

export const financeApi = {
  // Accounts
  async createAccount(data: {
    name: string;
    account_type: string;
    institution_name?: string | null;
    account_identifier?: string | null;
    currency?: string;
    opening_balance: string | number;
  }): Promise<FinancialAccount> {
    return financeRequest<FinancialAccount>('/api/v1/finance/accounts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async listAccounts(includeArchived: boolean = false): Promise<FinancialAccount[]> {
    return financeRequest<FinancialAccount[]>(
      `/api/v1/finance/accounts?include_archived=${includeArchived}`
    );
  },

  async getAccount(id: string): Promise<FinancialAccount> {
    return financeRequest<FinancialAccount>(`/api/v1/finance/accounts/${id}`);
  },

  async updateAccount(
    id: string,
    data: {
      name?: string;
      account_type?: string;
      institution_name?: string | null;
      account_identifier?: string | null;
    }
  ): Promise<FinancialAccount> {
    return financeRequest<FinancialAccount>(`/api/v1/finance/accounts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async updateOpeningBalance(
    id: string,
    openingBalance: string | number
  ): Promise<FinancialAccount> {
    return financeRequest<FinancialAccount>(
      `/api/v1/finance/accounts/${id}/opening-balance`,
      {
        method: 'PATCH',
        body: JSON.stringify({ opening_balance: openingBalance }),
      }
    );
  },

  async archiveAccount(id: string): Promise<FinancialAccount> {
    return financeRequest<FinancialAccount>(`/api/v1/finance/accounts/${id}/archive`, {
      method: 'POST',
    });
  },

  async restoreAccount(id: string): Promise<FinancialAccount> {
    return financeRequest<FinancialAccount>(`/api/v1/finance/accounts/${id}/restore`, {
      method: 'POST',
    });
  },

  async getAccountsSummary(): Promise<AccountSummary> {
    return financeRequest<AccountSummary>('/api/v1/finance/accounts/summary');
  },

  // Categories
  async listCategories(categoryType?: 'income' | 'expense'): Promise<FinancialCategory[]> {
    const query = categoryType ? `?category_type=${categoryType}` : '';
    return financeRequest<FinancialCategory[]>(`/api/v1/finance/categories${query}`);
  },

  async createCategory(data: {
    name: string;
    category_type: 'income' | 'expense';
    icon?: string | null;
    color?: string | null;
  }): Promise<FinancialCategory> {
    return financeRequest<FinancialCategory>('/api/v1/finance/categories', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async deleteCategory(id: string): Promise<void> {
    return financeRequest<void>(`/api/v1/finance/categories/${id}`, {
      method: 'DELETE',
    });
  },

  // Transactions
  async createTransaction(data: {
    account_id: string;
    transaction_type: 'income' | 'expense';
    amount: string | number;
    currency?: string;
    category_id?: string | null;
    description: string;
    merchant_payee?: string | null;
    transaction_date: string;
    notes?: string | null;
  }): Promise<FinancialTransaction> {
    return financeRequest<FinancialTransaction>('/api/v1/finance/transactions', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async listTransactions(params: {
    account_id?: string;
    transaction_type?: string;
    category_id?: string;
    source?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
    sort_by?: string;
    page?: number;
    page_size?: number;
  }): Promise<TransactionListResponse> {
    const q = new URLSearchParams();
    if (params.account_id) q.set('account_id', params.account_id);
    if (params.transaction_type) q.set('transaction_type', params.transaction_type);
    if (params.category_id) q.set('category_id', params.category_id);
    if (params.source) q.set('source', params.source);
    if (params.start_date) q.set('start_date', params.start_date);
    if (params.end_date) q.set('end_date', params.end_date);
    if (params.search) q.set('search', params.search);
    if (params.sort_by) q.set('sort_by', params.sort_by);
    if (params.page) q.set('page', String(params.page));
    if (params.page_size) q.set('page_size', String(params.page_size));

    return financeRequest<TransactionListResponse>(
      `/api/v1/finance/transactions?${q.toString()}`
    );
  },

  async getTransaction(id: string): Promise<FinancialTransaction> {
    return financeRequest<FinancialTransaction>(`/api/v1/finance/transactions/${id}`);
  },

  async updateTransaction(
    id: string,
    data: {
      amount?: string | number;
      category_id?: string | null;
      description?: string;
      merchant_payee?: string | null;
      transaction_date?: string;
      notes?: string | null;
    }
  ): Promise<FinancialTransaction> {
    return financeRequest<FinancialTransaction>(`/api/v1/finance/transactions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async deleteTransaction(id: string): Promise<void> {
    return financeRequest<void>(`/api/v1/finance/transactions/${id}`, {
      method: 'DELETE',
    });
  },

  // Transfers
  async executeTransfer(data: {
    source_account_id: string;
    destination_account_id: string;
    amount: string | number;
    currency?: string;
    transfer_date: string;
    description?: string;
  }): Promise<FinancialTransfer> {
    return financeRequest<FinancialTransfer>('/api/v1/finance/transfers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async listTransfers(limit: number = 50): Promise<FinancialTransfer[]> {
    return financeRequest<FinancialTransfer[]>(
      `/api/v1/finance/transfers?limit=${limit}`
    );
  },

  async reverseTransfer(id: string, reason: string): Promise<FinancialTransfer> {
    return financeRequest<FinancialTransfer>(
      `/api/v1/finance/transfers/${id}/reverse`,
      {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }
    );
  },

  // Dashboard
  async getDashboard(period: string = 'this_month'): Promise<FinancialDashboard> {
    return financeRequest<FinancialDashboard>(
      `/api/v1/finance/dashboard?period=${period}`
    );
  },

  // Banking Catalog & Connections
  async listBankInstitutions(params?: {
    search?: string;
    method?: string;
    category?: string;
    include_demo?: boolean;
  }): Promise<BankInstitutionCatalog> {
    const q = new URLSearchParams();
    if (params?.search) q.set('search', params.search);
    if (params?.method) q.set('method', params.method);
    if (params?.category) q.set('category', params.category);
    if (params?.include_demo !== undefined) q.set('include_demo', String(params.include_demo));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return financeRequest<BankInstitutionCatalog>(`/api/v1/banking/institutions${qs}`);
  },

  async initiateBankingConnection(
    bankId: string,
    connectionMethod: 'demo' | 'account_aggregator' = 'demo',
    consentGiven: boolean = false
  ): Promise<BankingConnection> {
    return financeRequest<BankingConnection>('/api/v1/banking/connections/initiate', {
      method: 'POST',
      body: JSON.stringify({
        bank_id: bankId,
        connection_method: connectionMethod,
        consent_given: consentGiven,
      }),
    });
  },

  async submitBankingConsent(
    connectionId: string,
    consentGiven: boolean,
    consentScope: string = 'accounts,transactions'
  ): Promise<BankingConnection> {
    return financeRequest<BankingConnection>(
      `/api/v1/banking/connections/${connectionId}/consent`,
      {
        method: 'POST',
        body: JSON.stringify({
          consent_given: consentGiven,
          consent_scope: consentScope,
        }),
      }
    );
  },

  async listBankingProviders(): Promise<BankingProviderInfo[]> {
    return financeRequest<BankingProviderInfo[]>('/api/v1/banking/providers');
  },

  async connectDemoProvider(
    providerId: string,
    consentGiven: boolean
  ): Promise<BankingConnection> {
    return financeRequest<BankingConnection>('/api/v1/banking/connections/demo', {
      method: 'POST',
      body: JSON.stringify({
        provider_id: providerId,
        consent_given: consentGiven,
      }),
    });
  },

  async listBankingConnections(): Promise<BankingConnection[]> {
    return financeRequest<BankingConnection[]>('/api/v1/banking/connections');
  },

  async getBankingConnection(id: string): Promise<BankingConnection> {
    return financeRequest<BankingConnection>(`/api/v1/banking/connections/${id}`);
  },

  async discoverBankingAccounts(connectionId: string): Promise<DiscoveredAccount[]> {
    return financeRequest<DiscoveredAccount[]>(
      `/api/v1/banking/connections/${connectionId}/accounts`
    );
  },

  async importBankingAccounts(
    connectionId: string,
    accountIds: string[],
    triggerInitialSync: boolean = false
  ): Promise<FinancialAccount[]> {
    return financeRequest<FinancialAccount[]>(
      `/api/v1/banking/connections/${connectionId}/accounts/import`,
      {
        method: 'POST',
        body: JSON.stringify({
          account_ids: accountIds,
          trigger_initial_sync: triggerInitialSync,
        }),
      }
    );
  },

  async syncBankingConnection(connectionId: string): Promise<BankingSyncResponse> {
    return financeRequest<BankingSyncResponse>(
      `/api/v1/banking/connections/${connectionId}/sync`,
      {
        method: 'POST',
      }
    );
  },

  async listBankingSyncRuns(connectionId: string): Promise<BankingSyncRun[]> {
    return financeRequest<BankingSyncRun[]>(
      `/api/v1/banking/connections/${connectionId}/sync-runs`
    );
  },

  async disconnectBankingConnection(connectionId: string): Promise<BankingConnection> {
    return financeRequest<BankingConnection>(
      `/api/v1/banking/connections/${connectionId}/disconnect`,
      {
        method: 'POST',
      }
    );
  },

  async revokeBankingConnection(connectionId: string): Promise<BankingConnection> {
    return financeRequest<BankingConnection>(
      `/api/v1/banking/connections/${connectionId}/revoke`,
      {
        method: 'POST',
      }
    );
  },
};
