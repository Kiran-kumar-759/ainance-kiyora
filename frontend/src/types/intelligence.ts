export interface CategorySummaryItem {
  category_name: string;
  transaction_count: number;
  total_amount: string | number;
  share_pct: string | number;
}

export interface OverviewMetricCard {
  total_analyzed_transactions: number;
  total_eligible_transactions: number;
  needs_review_count: number;
  confirmed_count: number;
  merchant_count: number;
  recurring_candidate_count: number;
  pending_recurring_count: number;
  open_anomaly_count: number;
  high_severity_anomaly_count: number;
  unread_insight_count: number;
  total_insight_count: number;
  ml_model_status: string;
  ml_model_version?: string | null;
  ml_training_samples: number;
  groq_enabled: boolean;
  groq_model: string;
  last_job_status?: string | null;
  last_job_completed_at?: string | null;
}

export interface AiModelMetadata {
  id: string;
  model_name: string;
  model_version: string;
  status: string;
  training_sample_count: number;
  class_count: number;
  accuracy?: string | number | null;
  precision_weighted?: string | number | null;
  recall_weighted?: string | number | null;
  f1_weighted?: string | number | null;
  confusion_matrix: {
    labels?: string[];
    matrix?: number[][];
    holdout_samples?: number;
  };
  evaluation_notes?: string | null;
  trained_at?: string | null;
  updated_at: string;
}

export interface AiProcessingJob {
  id: string;
  job_type: string;
  status: string;
  provider_name?: string | null;
  model_name?: string | null;
  prompt_version?: string | null;
  attempt_count: number;
  max_attempts: number;
  items_processed: number;
  summary: Record<string, unknown>;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface SpendingAnomaly {
  id: string;
  transaction_id?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  merchant_name?: string | null;
  anomaly_type: string;
  observed_amount: string | number;
  baseline_amount: string | number;
  deviation_pct: string | number;
  severity: 'low' | 'medium' | 'high' | string;
  confidence: string | number;
  detection_method: string;
  explanation: string;
  supporting_transaction_ids: string[];
  review_status: 'open' | 'acknowledged' | 'dismissed' | string;
  detected_at: string;
  reviewed_at?: string | null;
}

export interface FinancialInsight {
  id: string;
  insight_type: string;
  title: string;
  description: string;
  severity: string;
  period_start?: string | null;
  period_end?: string | null;
  supporting_data: Record<string, unknown>;
  calculation_method: string;
  provider_name?: string | null;
  confidence: string | number;
  suggested_action?: string | null;
  status: 'new' | 'read' | 'dismissed' | string;
  generated_at: string;
  read_at?: string | null;
  dismissed_at?: string | null;
}

export interface IntelligenceOverview {
  metrics: OverviewMetricCard;
  model_metadata?: AiModelMetadata | null;
  recent_jobs: AiProcessingJob[];
  top_categories: CategorySummaryItem[];
  top_anomalies: SpendingAnomaly[];
  top_insights: FinancialInsight[];
}

export interface TransactionCategorization {
  id: string;
  transaction_id: string;
  merchant_id?: string | null;
  transaction_date: string;
  transaction_type: 'income' | 'expense' | string;
  amount: string | number;
  currency: string;
  description?: string | null;
  merchant_payee?: string | null;
  normalized_merchant_name?: string | null;
  current_category_id?: string | null;
  current_category_name?: string | null;
  suggested_category_id?: string | null;
  suggested_category_name?: string | null;
  predicted_category_name?: string | null;
  classification_method: string;
  confidence: string | number;
  explanation?: string | null;
  evidence: Record<string, unknown>;
  model_version?: string | null;
  provider_name?: string | null;
  review_status: 'needs_review' | 'auto_categorized' | 'confirmed' | 'overridden' | 'dismissed' | string;
  analyzed_at: string;
  updated_at: string;
}

export interface TransactionCategorizationList {
  items: TransactionCategorization[];
  total: number;
  page: number;
  page_size: number;
  needs_review_count: number;
  confirmed_count: number;
}

export interface CategorizationFeedbackItem {
  id: string;
  transaction_id: string;
  categorization_id?: string | null;
  action: string;
  previous_category_id?: string | null;
  previous_category_name?: string | null;
  new_category_id?: string | null;
  new_category_name?: string | null;
  previous_merchant_name?: string | null;
  new_merchant_name?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface MerchantAliasItem {
  id: string;
  raw_pattern: string;
  normalized_token: string;
  occurrence_count: number;
  created_at: string;
}

export interface MerchantIdentityItem {
  id: string;
  canonical_key: string;
  normalized_name: string;
  default_category_id?: string | null;
  default_category_name?: string | null;
  is_user_confirmed: boolean;
  transaction_count: number;
  total_spent: string | number;
  aliases: MerchantAliasItem[];
  updated_at: string;
}

export interface MerchantList {
  items: MerchantIdentityItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface RecurringPaymentCandidate {
  id: string;
  merchant_id?: string | null;
  merchant_key: string;
  merchant_name: string;
  suggested_category_name?: string | null;
  commitment_type: string;
  frequency: string;
  estimated_amount: string | number;
  min_amount: string | number;
  max_amount: string | number;
  amount_variability_pct: string | number;
  is_variable_amount: boolean;
  occurrence_count: number;
  first_seen_date?: string | null;
  last_seen_date?: string | null;
  next_expected_date?: string | null;
  confidence: string | number;
  detection_method: string;
  evidence: Record<string, unknown>;
  review_status: 'pending' | 'confirmed' | 'rejected' | 'linked' | string;
  linked_subscription_id?: string | null;
  updated_at: string;
}

export interface RecurringCandidateList {
  items: RecurringPaymentCandidate[];
  total: number;
  pending_count: number;
  confirmed_count: number;
}

export interface SpendingPatternGroupItem {
  label: string;
  amount: string | number;
  transaction_count: number;
  share_pct: string | number;
}

export interface MonthlySpendingPoint {
  month: string;
  total_expense: string | number;
  total_income: string | number;
  recurring_expense: string | number;
  non_recurring_expense: string | number;
  transaction_count: number;
}

export interface WeeklySpendingPoint {
  week_start: string;
  total_expense: string | number;
  transaction_count: number;
}

export interface DayOfWeekSpendingPoint {
  day_name: string;
  day_index: number;
  total_expense: string | number;
  transaction_count: number;
}

export interface SpendingPatterns {
  period_start: string;
  period_end: string;
  total_expense: string | number;
  total_income: string | number;
  recurring_total: string | number;
  non_recurring_total: string | number;
  fixed_total: string | number;
  variable_total: string | number;
  essential_total: string | number;
  discretionary_total: string | number;
  weekend_expense: string | number;
  weekday_expense: string | number;
  weekend_share_pct: string | number;
  top_merchant_concentration_pct: string | number;
  top_3_merchant_concentration_pct: string | number;
  by_category: SpendingPatternGroupItem[];
  by_merchant: SpendingPatternGroupItem[];
  monthly_trend: MonthlySpendingPoint[];
  weekly_trend: WeeklySpendingPoint[];
  day_of_week_trend: DayOfWeekSpendingPoint[];
}

export interface SpendingAnomalyList {
  items: SpendingAnomaly[];
  total: number;
  open_count: number;
  acknowledged_count: number;
  dismissed_count: number;
}

export interface FinancialInsightList {
  items: FinancialInsight[];
  total: number;
  new_count: number;
  read_count: number;
  dismissed_count: number;
}
