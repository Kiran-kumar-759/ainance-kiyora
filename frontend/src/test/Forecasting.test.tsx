import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ForecastingPage } from '../pages/forecasting/ForecastingPage';
import { forecastingApi } from '../services/forecastingApi';

vi.mock('../services/forecastingApi', () => ({
  forecastingApi: {
    getOverview: vi.fn(),
    generateForecast: vi.fn(),
    runScenario: vi.fn(),
    listScenarios: vi.fn(),
    deleteScenario: vi.fn(),
    runAccuracyBacktest: vi.fn(),
    listEvaluations: vi.fn(),
  },
}));

const sampleOverview = {
  forecast: {
    id: 'fc-1',
    forecast_type: 'comprehensive',
    horizon_days: 30,
    as_of_date: '2026-11-25',
    data_cutoff_date: '2026-11-24',
    timezone: 'Asia/Kolkata',
    method: 'weighted_trend_seasonal_plus_commitments',
    method_version: '1.0',
    confidence_label: 'medium' as const,
    confidence_score: '0.6800',
    observation_count: 24,
    historical_days_covered: 90,
    status: 'completed',
    evaluation_status: 'pending_outcome',
    assumptions: ['Opening liquid balance is ₹1,20,000.00.'],
    limitations: ['Forecasts estimate future cash flows and never create ledger entries.'],
    generated_at: '2026-11-25T10:00:00Z',
  },
  cashflow: {
    horizon_days: 30,
    as_of_date: '2026-11-25',
    data_cutoff_date: '2026-11-24',
    timezone: 'Asia/Kolkata',
    method: 'weighted_trend_seasonal_plus_commitments',
    confidence_label: 'medium' as const,
    confidence_score: '0.6800',
    expected_income: '90000.00',
    expected_expense: '32000.00',
    known_commitments_total: '12000.00',
    unknown_variable_commitments_count: 1,
    predicted_net_cashflow: '58000.00',
    expected_opening_balance: '120000.00',
    projected_closing_balance: '178000.00',
    daily_points: [
      {
        label: '25 Nov',
        target_date: '2026-11-25',
        is_prediction: false,
        source_kind: 'historical_actual',
        income_amount: '0.00',
        expense_amount: '500.00',
        commitment_amount: '0.00',
        projected_closing_balance: '120000.00',
      },
      {
        label: '26 Nov',
        target_date: '2026-11-26',
        is_prediction: true,
        source_kind: 'known_commitment',
        income_amount: '3000.00',
        expense_amount: '1649.00',
        commitment_amount: '649.00',
        projected_closing_balance: '121351.00',
      },
    ],
    monthly_points: [],
    assumptions: ['Opening liquid balance is ₹1,20,000.00.'],
    limitations: ['Forecasts never alter confirmed transactions.'],
  },
  expenses: {
    horizon_days: 30,
    method: 'weighted_trend_seasonal_plus_commitments',
    confidence_label: 'medium' as const,
    confidence_score: '0.6800',
    predicted_total: '32000.00',
    lower_bound: '26000.00',
    upper_bound: '38000.00',
    historical_monthly_avg: '30000.00',
    recent_monthly_avg: '31500.00',
    trend_pct: '5.00',
    next_week_estimate: '7500.00',
    current_month_expected: '32000.00',
    next_month_estimate: '32000.00',
    quarterly_estimate: '96000.00',
    yearly_estimate: '384000.00',
    explanation: 'Based on 20 historical expenses.',
  },
  income: {
    horizon_days: 30,
    method: 'weighted_monthly_income',
    income_pattern: 'regular_monthly',
    confidence_label: 'high' as const,
    confidence_score: '0.8400',
    predicted_total: '90000.00',
    monthly_estimate: '90000.00',
    historical_monthly_avg: '90000.00',
    observation_count: 3,
    explanation: 'Classified income as regular monthly.',
  },
  categories: [
    {
      category_id: 'cat-1',
      category_name: 'Groceries',
      historical_monthly_avg: '10000.00',
      recent_monthly_spend: '11000.00',
      predicted_amount: '10500.00',
      lower_bound: '8500.00',
      upper_bound: '12500.00',
      expected_change_pct: '5.00',
      confidence_label: 'high' as const,
      data_sufficient: true,
      observation_count: 10,
      explanation: 'In line with historical monthly average.',
    },
  ],
  commitments: [
    {
      source_type: 'subscription',
      source_id: 'sub-1',
      name: 'Netflix UHD',
      due_date: '2026-12-05',
      frequency: 'monthly',
      expected_amount: '649.00',
      amount_certainty: 'confirmed_fixed',
      commitment_status: 'confirmed',
    },
    {
      source_type: 'bill',
      source_id: 'bill-2',
      name: 'BESCOM Meter',
      due_date: '2026-12-08',
      frequency: 'one_time',
      expected_amount: null,
      amount_certainty: 'unknown_amount',
      commitment_status: 'confirmed',
    },
  ],
  balances: [
    {
      account_id: 'acc-1',
      account_name: 'HDFC Main',
      account_type: 'savings',
      is_liability: false,
      current_balance: '120000.00',
      projected_end_balance: '178000.00',
      min_projected_balance: '119000.00',
      projected_change: '58000.00',
      confidence_label: 'medium' as const,
      assumptions: ['Liquid cash account'],
      points: [],
    },
    {
      account_id: 'acc-cc',
      account_name: 'HDFC Regalia Card',
      account_type: 'credit_card',
      is_liability: true,
      current_balance: '12000.00',
      projected_end_balance: '12000.00',
      confidence_label: 'medium' as const,
      assumptions: ['Liability exposure tracked separately'],
      points: [],
    },
  ],
  risks: [
    {
      risk_type: 'commitment_cluster',
      severity: 'medium' as const,
      title: '2 commitments fall in first week of December',
      description: 'Rent + EMI scheduled close together.',
      confidence_label: 'medium' as const,
      contributing_records: [],
    },
  ],
  savings: {
    horizon_days: 30,
    confidence_label: 'medium' as const,
    historical_monthly_savings: '60000.00',
    expected_monthly_savings: '58000.00',
    expected_savings_rate_pct: '64.44',
    projected_horizon_savings: '58000.00',
    projected_yearly_savings: '696000.00',
    conservative_monthly_savings: '48000.00',
    best_case_monthly_savings: '68000.00',
    disclaimer: 'Projected savings are estimates only.',
  },
  explanations: [
    {
      id: 'exp-1',
      explanation_type: 'expense_baseline',
      title: 'How your expected expenses were calculated',
      narrative: 'Based on 20 non-transfer expenses.',
      confidence_label: 'medium',
      supporting_refs: {},
    },
  ],
  is_stale: false,
};

describe('Phase 9 Financial Forecasting UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(forecastingApi.getOverview).mockResolvedValue(sampleOverview);
    vi.mocked(forecastingApi.listScenarios).mockResolvedValue([]);
    vi.mocked(forecastingApi.listEvaluations).mockResolvedValue([]);
  });

  it('renders forecasting dashboard, commitments, liability labels, scenario simulator, and backtesting', async () => {
    const onNavigate = vi.fn();
    vi.mocked(forecastingApi.runScenario).mockResolvedValue({
      id: 'scen-1',
      name: 'Monthly Expense Control',
      horizon_days: 30,
      parameters: {},
      baseline_summary: {
        expected_income: '90000.00',
        expected_expense: '32000.00',
        known_commitments: '12000.00',
        net_cashflow: '58000.00',
        projected_savings: '58000.00',
        projected_closing_balance: '178000.00',
      },
      scenario_summary: {
        expected_income: '90000.00',
        expected_expense: '28800.00',
        known_commitments: '12000.00',
        net_cashflow: '61200.00',
        projected_savings: '61200.00',
        projected_closing_balance: '181200.00',
      },
      delta_summary: { cashflow_diff: '3200.00' },
    });
    vi.mocked(forecastingApi.runAccuracyBacktest).mockResolvedValue({
      id: 'ev-1',
      forecast_type: 'comprehensive',
      horizon_days: 30,
      cutoff_date: '2026-10-26',
      eval_start_date: '2026-10-27',
      eval_end_date: '2026-11-25',
      method: 'weighted_trend_seasonal_plus_commitments',
      status: 'evaluated',
      predicted_expense: '31000.00',
      actual_expense: '30000.00',
      mae_expense: '1000.00',
      wape_expense_pct: '3.33',
      bias_expense: '1000.00',
      category_metrics: [],
      evaluated_at: '2026-11-25T10:00:00Z',
    });

    render(<ForecastingPage onNavigate={onNavigate} />);

    // Overview
    await waitFor(() => {
      expect(screen.getByText(/Financial Forecasting & Predictive Analytics/i)).toBeInTheDocument();
      expect(screen.getByText('₹90,000.00')).toBeInTheDocument();
      expect(screen.getByText('₹32,000.00')).toBeInTheDocument();
    });

    // Switch to Categories
    fireEvent.click(screen.getByRole('button', { name: /Expenses & Categories/i }));
    await waitFor(() => expect(screen.getByText('Groceries')).toBeInTheDocument());

    // Switch to Commitments & Balances (verify unknown variable & liability separation)
    fireEvent.click(screen.getByRole('button', { name: /Commitments & Balances/i }));
    await waitFor(() => {
      expect(screen.getByText('Unknown (Variable)')).toBeInTheDocument();
      expect(screen.getByText('Liability')).toBeInTheDocument();
    });

    // Switch to Savings & Risks
    fireEvent.click(screen.getByRole('button', { name: /Savings & Risks/i }));
    await waitFor(() =>
      expect(screen.getByText('2 commitments fall in first week of December')).toBeInTheDocument()
    );

    // Scenario Simulator submit
    fireEvent.click(screen.getByRole('button', { name: /Scenario Simulator/i }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Simulate Scenario/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Simulate Scenario/i }));
    await waitFor(() => expect(forecastingApi.runScenario).toHaveBeenCalled());

    // Accuracy & Backtesting
    fireEvent.click(screen.getByRole('button', { name: /Accuracy & Backtesting/i }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Run Walk-Forward Backtest/i })).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole('button', { name: /Run Walk-Forward Backtest/i }));
    await waitFor(() => expect(screen.getByText('3.33%')).toBeInTheDocument());
  });
});
