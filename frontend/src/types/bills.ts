export type BillCategory =
  | 'electricity'
  | 'water'
  | 'gas'
  | 'internet'
  | 'mobile_postpaid'
  | 'mobile_recharge'
  | 'rent'
  | 'insurance'
  | 'loan_emi'
  | 'credit_card'
  | 'maintenance'
  | 'other';

export type BillType = 'one_time' | 'recurring';
export type BillFrequency = 'weekly' | 'monthly' | 'quarterly' | 'half_yearly' | 'yearly' | 'custom';
export type PaymentMethod =
  | 'upi'
  | 'debit_card'
  | 'credit_card'
  | 'net_banking'
  | 'cash'
  | 'bank_transfer'
  | 'auto_debit'
  | 'other';

export interface NotificationChannels {
  in_app: boolean;
  email: boolean;
  sms: boolean;
}

export interface BillReminder {
  id: string;
  bill_id: string;
  offset_days: number;
  reminder_at: string;
  channels: string[];
  is_enabled: boolean;
  delivery_status: string;
  channel_outcomes: Record<string, { status: string; detail: string; provider?: string }>;
  retry_count: number;
  max_retries: number;
  next_retry_at?: string | null;
  last_attempt_at?: string | null;
  delivered_at?: string | null;
  idempotency_key: string;
}

export interface BillDocument {
  id: string;
  bill_id: string;
  original_filename: string;
  file_type: string;
  content_type: string;
  file_size: number;
  created_at: string;
}

export interface BillPayment {
  id: string;
  user_id: string;
  bill_id: string;
  bill_name?: string | null;
  financial_account_id?: string | null;
  account_name?: string | null;
  transaction_id?: string | null;
  transfer_id?: string | null;
  amount_paid: string | number;
  currency: string;
  payment_date: string;
  payment_method: string;
  reference_number?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface RecurrenceSchedule {
  id: string;
  bill_name: string;
  bill_category: string;
  provider_name?: string | null;
  frequency: BillFrequency;
  custom_interval_days?: number | null;
  anchor_day: number;
  is_variable_amount: boolean;
  expected_amount?: string | number | null;
  currency: string;
  start_date: string;
  end_date?: string | null;
  next_due_date: string;
  is_active: boolean;
}

export interface Bill {
  id: string;
  user_id: string;
  parent_schedule_id?: string | null;
  financial_category_id?: string | null;
  financial_category_name?: string | null;
  linked_account_id?: string | null;
  linked_account_name?: string | null;
  bill_name: string;
  bill_category: BillCategory;
  provider_name?: string | null;
  account_reference?: string | null;
  description?: string | null;
  bill_type: BillType;
  frequency?: BillFrequency | null;
  is_variable_amount: boolean;
  expected_amount?: string | number | null;
  current_amount?: string | number | null;
  amount_paid_total: string | number;
  remaining_due?: string | number | null;
  is_amount_unknown: boolean;
  currency: string;
  billing_period_start?: string | null;
  billing_period_end?: string | null;
  due_date: string;
  paid_at?: string | null;
  stored_status: string;
  derived_status: 'upcoming' | 'due_soon' | 'overdue' | 'paid' | 'partially_paid' | 'archived';
  days_until_due: number;
  preferred_payment_method?: string | null;
  reminder_enabled: boolean;
  reminder_days_before: number[];
  notification_channels: Record<string, boolean>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  payments: BillPayment[];
  reminders: BillReminder[];
  documents: BillDocument[];
  schedule?: RecurrenceSchedule | null;
}

export interface BillListResponse {
  items: Bill[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface BillsOverview {
  upcoming_count: number;
  due_soon_count: number;
  overdue_count: number;
  paid_count: number;
  total_upcoming_known_amount: string | number;
  total_overdue_known_amount: string | number;
  total_paid_amount: string | number;
  unknown_variable_bills_count: number;
  next_payment_due?: Bill | null;
  recent_payments: BillPayment[];
  unread_notifications_count: number;
  due_soon_threshold_days: number;
}

export interface AppNotification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  notification_type: string;
  related_bill_id?: string | null;
  related_payment_id?: string | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: AppNotification[];
  total: number;
  unread_count: number;
}

export interface ProcessRemindersResult {
  processed_count: number;
  delivered_count: number;
  partial_count: number;
  unavailable_count: number;
  failed_count: number;
  notifications_created: number;
  email_configured: boolean;
  sms_configured: boolean;
}
