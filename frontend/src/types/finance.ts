export type AccountType =
  | 'savings'
  | 'current'
  | 'cash'
  | 'credit_card'
  | 'digital_wallet'
  | 'other';

export type AccountStatus = 'active' | 'archived';
export type AccountSource = 'manual' | 'demo_bank';
export type TransactionType = 'income' | 'expense' | 'transfer';

export interface FinancialAccount {
  id: string;
  user_id: string;
  name: string;
  account_type: AccountType;
  institution_name?: string | null;
  account_identifier?: string | null;
  currency: string;
  opening_balance: string | number;
  current_balance: string | number;
  status: AccountStatus;
  source: AccountSource;
  created_at: string;
  updated_at: string;
}

export interface AccountSummary {
  total_accounts: number;
  active_accounts: number;
  total_assets: string | number;
  total_credit_liabilities: string | number;
  net_position: string | number;
}

export interface FinancialCategory {
  id: string;
  user_id?: string | null;
  name: string;
  category_type: 'income' | 'expense';
  icon?: string | null;
  color?: string | null;
  is_system: boolean;
  created_at: string;
}

export interface FinancialTransaction {
  id: string;
  user_id: string;
  account_id: string;
  account_name?: string | null;
  transaction_type: TransactionType;
  amount: string | number;
  currency: string;
  category_id?: string | null;
  category_name?: string | null;
  category_icon?: string | null;
  category_color?: string | null;
  description: string;
  merchant_payee?: string | null;
  transaction_date: string;
  notes?: string | null;
  source: string;
  external_reference?: string | null;
  transfer_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransactionListResponse {
  items: FinancialTransaction[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FinancialTransfer {
  id: string;
  user_id: string;
  source_account_id: string;
  source_account_name?: string | null;
  destination_account_id: string;
  destination_account_name?: string | null;
  amount: string | number;
  currency: string;
  transfer_date: string;
  description?: string | null;
  status: 'completed' | 'reversed';
  reversal_reason?: string | null;
  reversed_at?: string | null;
  created_at: string;
}

export interface FinancialDashboard {
  total_assets: string | number;
  total_liabilities: string | number;
  net_financial_position: string | number;
  account_count: number;
  period: string;
  period_start: string;
  period_end: string;
  total_income: string | number;
  total_expenses: string | number;
  net_savings: string | number;
  savings_rate_pct?: string | number | null;
  recent_transactions: FinancialTransaction[];
  accounts: FinancialAccount[];
}

export interface BankingProviderInfo {
  provider_id: string;
  name: string;
  description: string;
  is_simulated: boolean;
  logo_key: string;
  supported_account_types: string[];
}

export interface BankingConnection {
  id: string;
  provider_id: string;
  institution_name: string;
  status: 'connected' | 'disconnected' | 'error';
  consent_granted_at: string;
  is_simulated: boolean;
  last_sync_at?: string | null;
  created_at: string;
  connected_accounts_count: number;
}

export interface DiscoveredAccount {
  external_account_id: string;
  name: string;
  account_type: string;
  institution_name: string;
  masked_account_number: string;
  balance: string | number;
  currency: string;
  already_imported: boolean;
}

export interface BankingSyncResponse {
  connection_id: string;
  status: string;
  accounts_synced: number;
  transactions_synced: number;
  synced_at: string;
  message: string;
}

export interface BankingSyncRun {
  id: string;
  connection_id: string;
  status: string;
  accounts_synced: number;
  transactions_synced: number;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
}
