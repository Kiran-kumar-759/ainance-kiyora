import { BillReminder } from './bills';

export type SubscriptionCategory =
  | 'ott_streaming'
  | 'music'
  | 'cloud_storage'
  | 'software_saas'
  | 'gaming'
  | 'news_media'
  | 'fitness'
  | 'delivery_membership'
  | 'other';

export type SubscriptionFrequency =
  | 'weekly'
  | 'monthly'
  | 'quarterly'
  | 'half_yearly'
  | 'yearly'
  | 'custom';

export type SubscriptionStatus =
  | 'active'
  | 'trial'
  | 'paused'
  | 'cancelled'
  | 'expired'
  | 'archived';

export interface SubscriptionPriceHistory {
  id: string;
  subscription_id: string;
  previous_price?: string | number | null;
  new_price: string | number;
  effective_date: string;
  reason?: string | null;
  created_at: string;
}

export interface SubscriptionPayment {
  id: string;
  user_id: string;
  subscription_id: string;
  subscription_name?: string | null;
  financial_account_id?: string | null;
  account_name?: string | null;
  transaction_id?: string | null;
  transfer_id?: string | null;
  amount_paid: string | number;
  currency: string;
  payment_date: string;
  payment_method: string;
  reference_number?: string | null;
  payment_status: string;
  reversal_reason?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface Subscription {
  id: string;
  user_id: string;
  financial_category_id?: string | null;
  financial_category_name?: string | null;
  linked_account_id?: string | null;
  linked_account_name?: string | null;
  subscription_name: string;
  provider_name?: string | null;
  category: SubscriptionCategory;
  plan_name?: string | null;
  description?: string | null;
  notes?: string | null;
  amount?: string | number | null;
  monthly_equivalent?: string | number | null;
  annual_equivalent?: string | number | null;
  is_amount_unknown: boolean;
  currency: string;
  billing_frequency: SubscriptionFrequency;
  custom_interval_days?: number | null;
  anchor_day: number;
  start_date: string;
  next_renewal_date?: string | null;
  previous_renewal_date?: string | null;
  trial_start_date?: string | null;
  trial_end_date?: string | null;
  cancellation_date?: string | null;
  days_until_renewal?: number | null;
  is_renewal_due_soon: boolean;
  is_trial_ending_soon: boolean;
  preferred_payment_method?: string | null;
  status: SubscriptionStatus;
  reminder_enabled: boolean;
  reminder_days_before: number[];
  notification_channels: Record<string, boolean>;
  total_actual_paid: string | number;
  created_at: string;
  updated_at: string;
  price_history: SubscriptionPriceHistory[];
  payments: SubscriptionPayment[];
  reminders: BillReminder[];
}

export interface SubscriptionListResponse {
  items: Subscription[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SubscriptionOverview {
  active_count: number;
  trial_count: number;
  paused_count: number;
  cancelled_count: number;
  archived_count: number;
  renewals_due_soon_count: number;
  trials_ending_soon_count: number;
  unknown_price_active_count: number;
  monthly_recurring_cost: string | number;
  annual_recurring_cost: string | number;
  actual_spent_this_month: string | number;
  actual_spent_total: string | number;
  next_renewal_subscription?: Subscription | null;
  due_soon_threshold_days: number;
}

export interface SubscriptionAnalytics {
  monthly_recurring_cost: string | number;
  annual_recurring_cost: string | number;
  total_actual_historical_spend: string | number;
  active_subscriptions_count: number;
  cancelled_subscriptions_count: number;
  price_increase_events_count: number;
  by_category: {
    name: string;
    monthly_projected: string | number;
    annual_projected: string | number;
    actual_spent: string | number;
    count: number;
  }[];
  by_provider: {
    name: string;
    monthly_projected: string | number;
    annual_projected: string | number;
    actual_spent: string | number;
    count: number;
  }[];
  monthly_trend: {
    month: string;
    label: string;
    actual_spent: string | number;
    payment_count: number;
  }[];
  most_expensive: Subscription[];
  upcoming_commitments: Subscription[];
  recent_price_changes: SubscriptionPriceHistory[];
}

export interface SubscriptionCandidate {
  merchant_key: string;
  display_name: string;
  estimated_amount: string | number;
  detected_frequency: SubscriptionFrequency;
  occurrence_count: number;
  first_seen: string;
  last_seen: string;
  suggested_next_date: string;
  sample_transaction_ids: string[];
  confidence_note: string;
}

export type LoanType =
  | 'personal'
  | 'education'
  | 'home'
  | 'vehicle'
  | 'gold'
  | 'business'
  | 'consumer_durable'
  | 'other';

export type LoanStatus = 'active' | 'closed' | 'overdue' | 'paused' | 'archived';
export type InterestRateType = 'fixed' | 'floating';
export type CalculationMethod = 'reducing_balance' | 'flat_rate' | 'zero_interest';
export type EmiFrequency = 'monthly' | 'quarterly' | 'weekly';

export interface EmiScheduleRow {
  installment_number: number;
  due_date: string;
  opening_principal: string | number;
  emi_amount: string | number;
  principal_component: string | number;
  interest_component: string | number;
  closing_principal: string | number;
  is_final_adjustment: boolean;
}

export interface EmiCalculatorResult {
  principal: string | number;
  annual_interest_rate: string | number;
  tenure_installments: number;
  emi_frequency: string;
  calculation_method: string;
  periodic_emi: string | number;
  total_repayment: string | number;
  total_interest: string | number;
  principal_percentage: string | number;
  interest_percentage: string | number;
  assumptions: string[];
  preview_schedule: EmiScheduleRow[];
}

export interface LoanInstallment {
  id: string;
  loan_id: string;
  installment_number: number;
  due_date: string;
  opening_principal: string | number;
  emi_amount: string | number;
  principal_component: string | number;
  interest_component: string | number;
  closing_principal: string | number;
  principal_paid: string | number;
  interest_paid: string | number;
  status: string;
  derived_status: string;
  paid_date?: string | null;
  is_final_adjustment: boolean;
}

export interface LoanInterestRateHistory {
  id: string;
  loan_id: string;
  previous_rate?: string | number | null;
  new_rate: string | number;
  effective_date: string;
  previous_emi?: string | number | null;
  new_emi: string | number;
  remaining_tenure_months: number;
  reason?: string | null;
  created_at: string;
}

export interface LoanPayment {
  id: string;
  user_id: string;
  loan_id: string;
  loan_name?: string | null;
  installment_id?: string | null;
  payment_account_id?: string | null;
  account_name?: string | null;
  principal_transfer_id?: string | null;
  interest_transaction_id?: string | null;
  fee_transaction_id?: string | null;
  linked_transaction_id?: string | null;
  payment_type: string;
  payment_date: string;
  principal_paid: string | number;
  interest_paid: string | number;
  fee_paid: string | number;
  total_paid: string | number;
  reference_number?: string | null;
  payment_status: string;
  reversal_reason?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface Loan {
  id: string;
  user_id: string;
  liability_account_id: string;
  linked_repayment_account_id?: string | null;
  linked_repayment_account_name?: string | null;
  loan_name: string;
  lender_name: string;
  loan_type: LoanType;
  original_principal?: string | number | null;
  outstanding_principal_at_start: string | number;
  current_outstanding_principal: string | number;
  currency: string;
  interest_rate: string | number;
  interest_rate_type: InterestRateType;
  calculation_method: CalculationMethod;
  loan_start_date: string;
  tracking_start_date: string;
  first_emi_date: string;
  next_emi_due_date?: string | null;
  maturity_date?: string | null;
  original_tenure_months?: number | null;
  remaining_tenure_months: number;
  emi_amount: string | number;
  emi_frequency: EmiFrequency;
  anchor_day: number;
  loan_reference?: string | null;
  processing_fee?: string | number | null;
  prepayment_charges_info?: string | null;
  notes?: string | null;
  status: LoanStatus;
  derived_status: string;
  total_principal_repaid: string | number;
  total_interest_paid: string | number;
  total_paid_overall: string | number;
  repayment_progress_pct: string | number;
  overdue_installments_count: number;
  reminder_enabled: boolean;
  reminder_days_before: number[];
  notification_channels: Record<string, boolean>;
  created_at: string;
  updated_at: string;
  installments: LoanInstallment[];
  rate_history: LoanInterestRateHistory[];
  payments: LoanPayment[];
  reminders: BillReminder[];
}

export interface LoanListResponse {
  items: Loan[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LoanOverview {
  active_loans_count: number;
  closed_loans_count: number;
  overdue_loans_count: number;
  overdue_installments_count: number;
  total_outstanding_principal: string | number;
  total_original_principal_known?: string | number | null;
  total_monthly_emi_commitment: string | number;
  total_principal_repaid: string | number;
  total_interest_paid: string | number;
  next_emi_due_loan?: Loan | null;
}

export interface LoanPrepaymentScenario {
  is_scenario_simulation: boolean;
  disclaimer: string;
  current_outstanding_principal: string | number;
  baseline_emi: string | number;
  baseline_remaining_installments: number;
  baseline_remaining_interest: string | number;
  baseline_payoff_date?: string | null;
  scenario_revised_emi: string | number;
  scenario_remaining_installments: number;
  scenario_remaining_interest: string | number;
  scenario_payoff_date?: string | null;
  revised_principal_after_lump_sum: string | number;
  estimated_interest_saved: string | number;
  user_supplied_prepayment_fee: string | number;
  net_estimated_savings: string | number;
  tenure_months_saved: number;
}

export interface LoanAnalytics {
  total_outstanding_principal: string | number;
  total_principal_repaid: string | number;
  total_interest_paid: string | number;
  total_repayment_actual: string | number;
  projected_remaining_interest: string | number;
  monthly_emi_commitment: string | number;
  estimated_latest_maturity_date?: string | null;
  principal_share_pct: string | number;
  interest_share_pct: string | number;
  by_loan: {
    loan_id: string;
    loan_name: string;
    lender_name: string;
    loan_type: string;
    outstanding_principal: string | number;
    principal_repaid: string | number;
    interest_paid: string | number;
    emi_amount: string | number;
    progress_pct: string | number;
    maturity_date?: string | null;
    status: string;
  }[];
  repayment_trend: {
    month: string;
    label: string;
    principal: number;
    interest: number;
  }[];
}
