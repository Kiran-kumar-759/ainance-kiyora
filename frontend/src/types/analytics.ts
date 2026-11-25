import { FinancialAccount, FinancialTransaction } from './finance';

export interface PeriodBounds {
  period: string;
  label: string;
  start_date: string;
  end_date: string;
  timezone: string;
  is_partial_period: boolean;
  days_in_period: number;
  elapsed_days: number;
}

export interface CalculationMetadata {
  formula: string;
  included_transaction_count: number;
  excluded_transfer_count: number;
  excluded_reversed_count: number;
  currency: string;
  notes?: string | null;
}

export interface ComparisonMetric {
  current_value: string | number;
  previous_value: string | number;
  absolute_difference: string | number;
  percentage_change?: string | number | null;
  trend_direction: 'up' | 'down' | 'flat';
  is_zero_baseline: boolean;
  comparison_note?: string | null;
}

export interface TimeSeriesPoint {
  bucket_key: string;
  label: string;
  start_date: string;
  end_date: string;
  income: string | number;
  expenses: string | number;
  net_savings: string | number;
  savings_rate_pct?: string | number | null;
}

export interface CategoryBreakdownItem {
  category_id?: string | null;
  category_name: string;
  category_color?: string | null;
  total_amount: string | number;
  percentage: string | number;
  transaction_count: number;
  average_amount: string | number;
}

export interface SourceDistributionItem {
  source: string;
  label: string;
  total_amount: string | number;
  percentage: string | number;
  transaction_count: number;
}

export interface AccountBreakdownItem {
  account_id: string;
  account_name: string;
  account_type: string;
  total_amount: string | number;
  percentage: string | number;
  transaction_count: number;
}

export interface BalanceTrendPoint {
  date: string;
  label: string;
  assets_balance: string | number;
  liabilities_balance: string | number;
  net_position: string | number;
}

export interface AccountAnalyticsItem {
  account_id: string;
  name: string;
  institution_name?: string | null;
  account_type: string;
  current_balance: string | number;
  is_liability: boolean;
  currency: string;
  source: string;
  status: string;
  transaction_count: number;
  period_income: string | number;
  period_expenses: string | number;
  net_transaction_activity: string | number;
}

export interface AnalyticsDashboard {
  total_assets: string | number;
  total_liabilities: string | number;
  net_financial_position: string | number;
  account_count: number;
  balance_as_of_note: string;
  period_bounds: PeriodBounds;
  total_income: string | number;
  total_expenses: string | number;
  net_savings: string | number;
  savings_rate_pct?: string | number | null;
  income_comparison: ComparisonMetric;
  expense_comparison: ComparisonMetric;
  savings_comparison: ComparisonMetric;
  income_vs_expense_series: TimeSeriesPoint[];
  spending_by_category: CategoryBreakdownItem[];
  monthly_spending_trend: TimeSeriesPoint[];
  account_balances: AccountAnalyticsItem[];
  accounts: FinancialAccount[];
  recent_transactions: FinancialTransaction[];
  is_empty_state: boolean;
  traceability: CalculationMetadata;
}

export interface IncomeAnalyticsResponse {
  period_bounds: PeriodBounds;
  granularity: string;
  total_income: string | number;
  transaction_count: number;
  by_category: CategoryBreakdownItem[];
  by_account: AccountBreakdownItem[];
  by_source: SourceDistributionItem[];
  trend: TimeSeriesPoint[];
  comparison: ComparisonMetric;
  traceability: CalculationMetadata;
}

export interface ExpenseAnalyticsResponse {
  period_bounds: PeriodBounds;
  granularity: string;
  total_expenses: string | number;
  transaction_count: number;
  average_daily_spend: string | number;
  average_monthly_spend?: string | number | null;
  by_category: CategoryBreakdownItem[];
  by_account: AccountBreakdownItem[];
  by_source: SourceDistributionItem[];
  trend: TimeSeriesPoint[];
  largest_expenses: FinancialTransaction[];
  comparison: ComparisonMetric;
  traceability: CalculationMetadata;
}

export interface CashFlowAnalyticsResponse {
  period_bounds: PeriodBounds;
  granularity: string;
  total_income: string | number;
  total_expenses: string | number;
  net_cash_flow: string | number;
  savings_rate_pct?: string | number | null;
  series: TimeSeriesPoint[];
  traceability: CalculationMetadata;
}

export interface CategoryAnalyticsResponse {
  period_bounds: PeriodBounds;
  category_type: 'expense' | 'income';
  total_amount: string | number;
  transaction_count: number;
  items: CategoryBreakdownItem[];
  traceability: CalculationMetadata;
}

export interface TrendAnalyticsResponse {
  period_bounds: PeriodBounds;
  granularity: string;
  series: TimeSeriesPoint[];
  top_category_trends: {
    category_id?: string | null;
    category_name: string;
    category_color?: string | null;
    total_amount: string;
    points: { label: string; amount: string }[];
  }[];
  balance_history: BalanceTrendPoint[];
  balance_history_available: boolean;
  balance_history_note: string;
  traceability: CalculationMetadata;
}

export interface PeriodComparisonResponse {
  comparison_preset: string;
  current_period: PeriodBounds;
  previous_period: PeriodBounds;
  income: ComparisonMetric;
  expenses: ComparisonMetric;
  net_savings: ComparisonMetric;
  savings_rate_current?: string | number | null;
  savings_rate_previous?: string | number | null;
  category_comparisons: {
    category_id?: string | null;
    category_name: string;
    category_color?: string | null;
    comparison: ComparisonMetric;
  }[];
  partial_period_warning?: string | null;
}

export interface AccountAnalyticsListResponse {
  period_bounds: PeriodBounds;
  total_assets: string | number;
  total_liabilities: string | number;
  net_financial_position: string | number;
  accounts: AccountAnalyticsItem[];
}

export interface AccountAnalyticsDetailResponse {
  period_bounds: PeriodBounds;
  granularity: string;
  account: AccountAnalyticsItem;
  trend: TimeSeriesPoint[];
  category_distribution: CategoryBreakdownItem[];
  recent_transactions: FinancialTransaction[];
  balance_history: BalanceTrendPoint[];
  balance_history_note: string;
  traceability: CalculationMetadata;
}

export type ReportType =
  | 'monthly_summary'
  | 'income_report'
  | 'expense_report'
  | 'category_spending'
  | 'account_activity'
  | 'cash_flow'
  | 'savings_report'
  | 'transaction_summary';

export interface ReportDefinition {
  id: ReportType;
  title: string;
  description: string;
  supports_csv_export: boolean;
}

export interface FinancialReportResponse {
  metadata: {
    report_type: ReportType;
    title: string;
    start_date: string;
    end_date: string;
    account_id?: string | null;
    account_name?: string | null;
    transaction_type?: string | null;
    category_id?: string | null;
    category_name?: string | null;
    source?: string | null;
    generated_at: string;
    currency: string;
    timezone: string;
  };
  summary_metrics: {
    label: string;
    value: string;
    raw_decimal?: string | number | null;
    highlight: 'neutral' | 'positive' | 'negative';
  }[];
  category_breakdown: CategoryBreakdownItem[];
  account_breakdown: AccountBreakdownItem[];
  cashflow_series: TimeSeriesPoint[];
  transactions: FinancialTransaction[];
  total_transactions: number;
  traceability: CalculationMetadata;
}

export interface TransactionNavigationFilters {
  accountId?: string;
  categoryId?: string;
  transactionType?: string;
  startDate?: string;
  endDate?: string;
  source?: string;
}
