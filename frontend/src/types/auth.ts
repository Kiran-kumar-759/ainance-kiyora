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
    monthly_summary?: boolean;
    [key: string]: boolean | undefined;
  };
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
