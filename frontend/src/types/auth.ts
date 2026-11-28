export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_email_verified: boolean;
  onboarding_completed: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserPreferences {
  preferred_currency: string;
  locale: string;
  timezone: string;
  date_format: string;
  notification_preferences: {
    email_alerts?: boolean;
    bill_reminders?: boolean;
    subscription_reminders?: boolean;
    loan_emi_reminders?: boolean;
    payment_due_reminders?: boolean;
    financial_insights?: boolean;
    spending_anomalies?: boolean;
    forecast_notifications?: boolean;
    monthly_summary?: boolean;
    email_reminders_enabled?: boolean;
    sms_reminders_enabled?: boolean;
    phone_number?: string;
    number_format?: string;
    week_start?: 'monday' | 'sunday';
    language?: string;
    default_landing_view?: 'dashboard' | 'analytics' | 'assistant' | 'bills' | 'transactions';
    compact_sidebar?: boolean;
    [key: string]: string | boolean | null | undefined;
  };
}

export interface PrivacyDataSummary {
  accounts_count: number;
  transactions_count: number;
  bills_count: number;
  subscriptions_count: number;
  loans_count: number;
  documents_count: number;
  conversations_count: number;
  forecast_scenarios_count: number;
  banking_connections_count: number;
  email_connections_count: number;
  data_storage_disclosures: string[];
  export_endpoints: { label: string; endpoint: string; description: string }[];
  account_deletion_status: string;
  account_deletion_note: string;
}

export interface UserSession {
  id: string;
  created_at: string;
  expires_at: string;
  last_used_at: string;
  user_agent: string | null;
  ip_address: string | null;
  is_current: boolean;
}

export interface OnboardingStatus {
  onboarding_completed: boolean;
  is_email_verified: boolean;
  full_name: string;
  current_step?: number;
  current_stage?: string;
  dashboard_access_allowed?: boolean;
  preferences: UserPreferences;
}

export type FinancialSetupMethod =
  | 'bank_connect'
  | 'manual_account'
  | 'statement_import'
  | 'document_upload'
  | 'skip';

export interface InitializationStepStatus {
  key: string;
  label: string;
  status: 'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed';
  detail?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface InitializationStatus {
  initialization_status: 'not_started' | 'in_progress' | 'completed' | 'failed';
  initialization_error?: string | null;
  initialization_started_at?: string | null;
  initialization_completed_at?: string | null;
  steps: InitializationStepStatus[];
  dashboard_access_allowed: boolean;
  onboarding_completed: boolean;
  current_stage: string;
  summary: Record<string, string | number | boolean | null | undefined>;
}

export interface OnboardingProfileSummary {
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone_number?: string | null;
  country: string;
  financial_year: string;
  monthly_budget?: string | number | null;
  monthly_income_range?: string | null;
  financial_goals: string[];
}

export interface OnboardingProfileRequest {
  first_name?: string;
  last_name?: string;
  full_name?: string;
  phone_number?: string;
  preferred_currency?: string;
  locale?: string;
  timezone?: string;
  date_format?: string;
  monthly_budget?: string | number;
  monthly_income_range?: string;
  financial_goals?: string[];
  notification_preferences?: Record<string, unknown>;
}

export interface OnboardingComprehensiveStatus {
  user_id: string;
  onboarding_completed: boolean;
  dashboard_access_allowed: boolean;
  required_gate_view: 'onboarding' | 'dashboard';
  is_email_verified: boolean;
  current_stage: string;
  completed_stages: string[];
  current_step: number;
  profile_completed: boolean;
  profile: OnboardingProfileSummary;
  financial_setup_status: string;
  selected_setup_method?: string | null;
  financial_setup_skipped: boolean;
  has_active_banking_connection: boolean;
  accounts_count: number;
  transactions_count: number;
  pending_import_batches_count: number;
  pending_documents_count: number;
  initialization_status: 'not_started' | 'in_progress' | 'completed' | 'failed';
  initialization_steps: InitializationStepStatus[];
  initialization_error?: string | null;
  next_action: string;
  guidance_message: string;
  preferences: UserPreferences;
}

export interface DashboardAccessResponse {
  allowed: boolean;
  onboarding_completed: boolean;
  current_stage: string;
  required_gate_view: 'onboarding' | 'dashboard';
  next_action: string;
  message: string;
}

export interface AuthResponse {
  message: string;
  user: User;
  email_delivery_status: 'sent' | 'failed' | 'skipped' | 'verified';
}

export interface MessageResponse {
  message: string;
}
