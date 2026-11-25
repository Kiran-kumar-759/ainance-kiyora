export type ConfidenceLabel = 'high' | 'medium' | 'low' | 'insufficient_data';

export interface CashflowPeriodPoint {
  label: string;
  target_date: string;
  is_prediction: boolean;
  source_kind: 'historical_actual' | 'known_commitment' | 'statistical_prediction' | string;
  income_amount?: string | number | null;
  expense_amount?: string | number | null;
  commitment_amount?: string | number | null;
  net_cashflow?: string | number | null;
  lower_bound?: string | number | null;
  upper_bound?: string | number | null;
  projected_closing_balance?: string | number | null;
}

export interface CashflowForecast {
  horizon_days: number;
  as_of_date: string;
  data_cutoff_date?: string | null;
  timezone: string;
  method: string;
  confidence_label: ConfidenceLabel;
  confidence_score: string | number;
  expected_income?: string | number | null;
  expected_expense?: string | number | null;
  known_commitments_total: string | number;
  unknown_variable_commitments_count: number;
  predicted_net_cashflow?: string | number | null;
  expected_opening_balance: string | number;
  projected_closing_balance?: string | number | null;
  daily_points: CashflowPeriodPoint[];
  monthly_points: CashflowPeriodPoint[];
  assumptions: string[];
  limitations: string[];
}

export interface ExpenseForecast {
  horizon_days: number;
  method: string;
  confidence_label: ConfidenceLabel;
  confidence_score: string | number;
  predicted_total?: string | number | null;
  lower_bound?: string | number | null;
  upper_bound?: string | number | null;
  historical_monthly_avg?: string | number | null;
  recent_monthly_avg?: string | number | null;
  trend_pct?: string | number | null;
  next_week_estimate?: string | number | null;
  current_month_expected?: string | number | null;
  next_month_estimate?: string | number | null;
  quarterly_estimate?: string | number | null;
  yearly_estimate?: string | number | null;
  explanation: string;
}

export interface IncomeForecast {
  horizon_days: number;
  method: string;
  income_pattern: string;
  confidence_label: ConfidenceLabel;
  confidence_score: string | number;
  predicted_total?: string | number | null;
  lower_bound?: string | number | null;
  upper_bound?: string | number | null;
  monthly_estimate?: string | number | null;
  historical_monthly_avg?: string | number | null;
  observation_count: number;
  explanation: string;
}

export interface CategoryForecastItem {
  category_id?: string | null;
  category_name: string;
  historical_monthly_avg: string | number;
  recent_monthly_spend: string | number;
  predicted_amount?: string | number | null;
  lower_bound?: string | number | null;
  upper_bound?: string | number | null;
  expected_change_pct?: string | number | null;
  confidence_label: ConfidenceLabel;
  data_sufficient: boolean;
  observation_count: number;
  explanation: string;
}

export interface CommitmentForecastItem {
  source_type: string;
  source_id: string;
  name: string;
  due_date: string;
  frequency: string;
  expected_amount?: string | number | null;
  amount_certainty: string;
  commitment_status: string;
  category_name?: string | null;
  account_id?: string | null;
  account_name?: string | null;
}

export interface AccountBalanceProjectionPoint {
  target_date: string;
  label: string;
  projected_balance: string | number;
  is_prediction: boolean;
}

export interface AccountBalanceForecastItem {
  account_id: string;
  account_name: string;
  account_type: string;
  is_liability: boolean;
  current_balance: string | number;
  projected_end_balance?: string | number | null;
  min_projected_balance?: string | number | null;
  projected_change?: string | number | null;
  confidence_label: ConfidenceLabel;
  assumptions: string[];
  points: AccountBalanceProjectionPoint[];
}

export interface RiskWarningItem {
  risk_type: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  target_date?: string | null;
  projected_impact_amount?: string | number | null;
  confidence_label: ConfidenceLabel;
  contributing_records: Array<{ type: string; id: string; name: string }>;
}

export interface SavingsForecast {
  horizon_days: number;
  confidence_label: ConfidenceLabel;
  historical_monthly_savings?: string | number | null;
  expected_monthly_savings?: string | number | null;
  expected_savings_rate_pct?: string | number | null;
  projected_horizon_savings?: string | number | null;
  projected_yearly_savings?: string | number | null;
  conservative_monthly_savings?: string | number | null;
  best_case_monthly_savings?: string | number | null;
  disclaimer: string;
}

export interface ForecastExplanationItem {
  id: string;
  explanation_type: string;
  title: string;
  narrative: string;
  confidence_label: string;
  supporting_refs: Record<string, unknown>;
}

export interface ForecastRecord {
  id: string;
  forecast_type: string;
  horizon_days: number;
  as_of_date: string;
  data_cutoff_date?: string | null;
  timezone: string;
  method: string;
  method_version: string;
  confidence_label: ConfidenceLabel;
  confidence_score: string | number;
  observation_count: number;
  historical_days_covered: number;
  status: string;
  evaluation_status: string;
  assumptions: string[];
  limitations: string[];
  generated_at: string;
}

export interface ForecastingOverview {
  forecast: ForecastRecord;
  cashflow: CashflowForecast;
  expenses: ExpenseForecast;
  income: IncomeForecast;
  categories: CategoryForecastItem[];
  commitments: CommitmentForecastItem[];
  balances: AccountBalanceForecastItem[];
  risks: RiskWarningItem[];
  savings: SavingsForecast;
  explanations: ForecastExplanationItem[];
  is_stale: boolean;
}

export interface ForecastScenarioOutcome {
  expected_income: string | number;
  expected_expense: string | number;
  known_commitments: string | number;
  net_cashflow: string | number;
  projected_savings: string | number;
  projected_closing_balance: string | number;
}

export interface ForecastScenario {
  id?: string | null;
  name: string;
  horizon_days: number;
  parameters: Record<string, unknown>;
  baseline_summary: ForecastScenarioOutcome;
  scenario_summary: ForecastScenarioOutcome;
  delta_summary: Record<string, string | number>;
  created_at?: string | null;
}

export interface CategoryEvaluationMetric {
  category_name: string;
  predicted_amount: string | number;
  actual_amount: string | number;
  absolute_error: string | number;
}

export interface ForecastEvaluation {
  id: string;
  forecast_type: string;
  horizon_days: number;
  cutoff_date: string;
  eval_start_date: string;
  eval_end_date: string;
  method: string;
  status: string;
  predicted_expense?: string | number | null;
  actual_expense?: string | number | null;
  predicted_income?: string | number | null;
  actual_income?: string | number | null;
  predicted_net?: string | number | null;
  actual_net?: string | number | null;
  mae_expense?: string | number | null;
  rmse_expense?: string | number | null;
  wape_expense_pct?: string | number | null;
  bias_expense?: string | number | null;
  category_metrics: CategoryEvaluationMetric[];
  notes?: string | null;
  evaluated_at: string;
}
