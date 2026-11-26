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
  preferences: UserPreferences;
}

export interface AuthResponse {
  message: string;
  user: User;
  email_delivery_status: 'sent' | 'failed' | 'skipped' | 'verified';
}

export interface MessageResponse {
  message: string;
}
