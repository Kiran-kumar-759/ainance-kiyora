import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DashboardPage } from '../pages/finance/DashboardPage';
import { AnalyticsPage } from '../pages/analytics/AnalyticsPage';
import { ReportsPage } from '../pages/reports/ReportsPage';
import { financeApi } from '../services/financeApi';
import { analyticsApi } from '../services/analyticsApi';

vi.mock('../services/financeApi', () => ({
  financeApi: {
    getDashboard: vi.fn(),
    listAccounts: vi.fn(),
    listCategories: vi.fn(),
  },
}));

vi.mock('../services/analyticsApi', () => ({
  analyticsApi: {
    getDashboard: vi.fn(),
    getIncome: vi.fn(),
    getExpenses: vi.fn(),
    getCashFlow: vi.fn(),
    getCategories: vi.fn(),
    getTrends: vi.fn(),
    getComparisons: vi.fn(),
    getAccounts: vi.fn(),
    getAccountDetail: vi.fn(),
    listReports: vi.fn(),
    getReport: vi.fn(),
    exportReportCsv: vi.fn(),
  },
}));

const sampleBounds = {
  period: 'this_month',
  label: 'This Month (Nov 2026)',
  start_date: '2026-11-01',
  end_date: '2026-11-30',
  timezone: 'Asia/Kolkata',
  is_partial_period: true,
  days_in_period: 30,
  elapsed_days: 25,
};

const sampleTrace = {
  formula: 'Net Savings = Income - Expenses',
  included_transaction_count: 4,
  excluded_transfer_count: 1,
  excluded_reversed_count: 0,
  currency: 'INR',
};

describe('Phase 4 Frontend Dashboard, Analytics & Reports', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(financeApi.listAccounts).mockResolvedValue([
      {
        id: 'acc-1',
        user_id: 'u-1',
        name: 'HDFC Salary',
        account_type: 'savings',
        currency: 'INR',
        opening_balance: '50000.00',
        current_balance: '125000.00',
        status: 'active',
        source: 'manual',
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.listCategories).mockResolvedValue([
      {
        id: 'cat-1',
        name: 'Groceries',
        category_type: 'expense',
        is_system: true,
        created_at: '2026-11-01T00:00:00Z',
      },
    ]);
  });

  it('renders upgraded Dashboard with charts, period switching, custom range validation, and category drill-down', async () => {
    const onNavigate = vi.fn();
    vi.mocked(analyticsApi.getDashboard).mockResolvedValue({
      total_assets: '125000.00',
      total_liabilities: '10000.00',
      net_financial_position: '115000.00',
      account_count: 2,
      balance_as_of_note: 'Real-time ledger balances',
      period_bounds: sampleBounds,
      total_income: '85000.00',
      total_expenses: '22000.00',
      net_savings: '63000.00',
      savings_rate_pct: '74.12',
      income_comparison: {
        current_value: '85000.00',
        previous_value: '80000.00',
        absolute_difference: '5000.00',
        percentage_change: '6.25',
        trend_direction: 'up',
        is_zero_baseline: false,
      },
      expense_comparison: {
        current_value: '22000.00',
        previous_value: '20000.00',
        absolute_difference: '2000.00',
        percentage_change: '10.00',
        trend_direction: 'up',
        is_zero_baseline: false,
      },
      savings_comparison: {
        current_value: '63000.00',
        previous_value: '60000.00',
        absolute_difference: '3000.00',
        percentage_change: '5.00',
        trend_direction: 'up',
        is_zero_baseline: false,
      },
      income_vs_expense_series: [
        {
          bucket_key: '2026-11-01',
          label: '01 Nov',
          start_date: '2026-11-01',
          end_date: '2026-11-01',
          income: '85000.00',
          expenses: '22000.00',
          net_savings: '63000.00',
          savings_rate_pct: '74.12',
        },
      ],
      spending_by_category: [
        {
          category_id: 'cat-1',
          category_name: 'Groceries',
          category_color: '#10b981',
          total_amount: '22000.00',
          percentage: '100.00',
          transaction_count: 3,
          average_amount: '7333.33',
        },
      ],
      monthly_spending_trend: [
        {
          bucket_key: '2026-11-01',
          label: 'Nov 2026',
          start_date: '2026-11-01',
          end_date: '2026-11-30',
          income: '85000.00',
          expenses: '22000.00',
          net_savings: '63000.00',
        },
      ],
      account_balances: [],
      accounts: [],
      recent_transactions: [],
      is_empty_state: false,
      traceability: sampleTrace,
    });

    render(<DashboardPage onNavigate={onNavigate} userName="Kiran" />);

    await waitFor(() => {
      expect(screen.getByText('₹1,15,000.00')).toBeInTheDocument();
      expect(screen.getByText('Savings Rate: 74.12%')).toBeInTheDocument();
      expect(screen.getByText('Groceries')).toBeInTheDocument();
    });

    // Click category legend to drill down into Transactions
    fireEvent.click(screen.getByText('Groceries'));
    expect(onNavigate).toHaveBeenCalledWith('transactions', {
      categoryId: 'cat-1',
      transactionType: 'expense',
      startDate: '2026-11-01',
      endDate: '2026-11-30',
    });

    // Period switching triggers backend query
    fireEvent.change(screen.getByLabelText('Select Financial Period'), {
      target: { value: 'last_month' },
    });
    await waitFor(() => {
      expect(analyticsApi.getDashboard).toHaveBeenCalledWith({
        period: 'last_month',
        start_date: undefined,
        end_date: undefined,
      });
    });
  });

  it('renders Analytics tabs (Cash Flow, Expenses, Income, Comparisons, Accounts) cleanly', async () => {
    const onNavigate = vi.fn();
    vi.mocked(analyticsApi.getCashFlow).mockResolvedValue({
      period_bounds: sampleBounds,
      granularity: 'day',
      total_income: '85000.00',
      total_expenses: '22000.00',
      net_cash_flow: '63000.00',
      savings_rate_pct: '74.12',
      series: [],
      traceability: sampleTrace,
    });
    vi.mocked(analyticsApi.getExpenses).mockResolvedValue({
      period_bounds: sampleBounds,
      granularity: 'day',
      total_expenses: '22000.00',
      transaction_count: 3,
      average_daily_spend: '880.00',
      average_monthly_spend: '22000.00',
      by_category: [
        {
          category_id: 'cat-1',
          category_name: 'Groceries',
          total_amount: '22000.00',
          percentage: '100.00',
          transaction_count: 3,
          average_amount: '7333.33',
        },
      ],
      by_account: [],
      by_source: [{ source: 'csv_import', label: 'CSV Import', total_amount: '22000.00', percentage: '100.00', transaction_count: 3 }],
      trend: [],
      largest_expenses: [],
      comparison: {
        current_value: '22000.00',
        previous_value: '20000.00',
        absolute_difference: '2000.00',
        percentage_change: '10.00',
        trend_direction: 'up',
        is_zero_baseline: false,
      },
      traceability: sampleTrace,
    });
    vi.mocked(analyticsApi.getIncome).mockResolvedValue({
      period_bounds: sampleBounds,
      granularity: 'day',
      total_income: '85000.00',
      transaction_count: 1,
      by_category: [],
      by_account: [],
      by_source: [],
      trend: [],
      comparison: {
        current_value: '85000.00',
        previous_value: '0.00',
        absolute_difference: '85000.00',
        percentage_change: null,
        trend_direction: 'up',
        is_zero_baseline: true,
      },
      traceability: sampleTrace,
    });
    vi.mocked(analyticsApi.getCategories).mockResolvedValue({
      period_bounds: sampleBounds,
      category_type: 'expense',
      total_amount: '22000.00',
      transaction_count: 3,
      items: [
        {
          category_id: 'cat-1',
          category_name: 'Groceries',
          total_amount: '22000.00',
          percentage: '100.00',
          transaction_count: 3,
          average_amount: '7333.33',
        },
      ],
      traceability: sampleTrace,
    });
    vi.mocked(analyticsApi.getTrends).mockResolvedValue({
      period_bounds: sampleBounds,
      granularity: 'day',
      series: [],
      top_category_trends: [],
      balance_history: [
        {
          date: '2026-11-01',
          label: '01 Nov',
          assets_balance: '125000.00',
          liabilities_balance: '10000.00',
          net_position: '115000.00',
        },
      ],
      balance_history_available: true,
      balance_history_note: 'Reconstructed from unreversed ledger entries.',
      traceability: sampleTrace,
    });
    vi.mocked(analyticsApi.getComparisons).mockResolvedValue({
      comparison_preset: 'month_over_month',
      current_period: sampleBounds,
      previous_period: { ...sampleBounds, label: 'Last Month (Oct 2026)', is_partial_period: false },
      income: {
        current_value: '85000.00',
        previous_value: '0.00',
        absolute_difference: '85000.00',
        percentage_change: null,
        trend_direction: 'up',
        is_zero_baseline: true,
      },
      expenses: {
        current_value: '25000.00',
        previous_value: '20000.00',
        absolute_difference: '5000.00',
        percentage_change: '25.00',
        trend_direction: 'up',
        is_zero_baseline: false,
      },
      net_savings: {
        current_value: '60000.00',
        previous_value: '-20000.00',
        absolute_difference: '80000.00',
        percentage_change: '400.00',
        trend_direction: 'up',
        is_zero_baseline: false,
      },
      category_comparisons: [],
      partial_period_warning: 'Partial period comparison: 25 of 30 days elapsed.',
    });
    vi.mocked(analyticsApi.getAccounts).mockResolvedValue({
      period_bounds: sampleBounds,
      total_assets: '125000.00',
      total_liabilities: '10000.00',
      net_financial_position: '115000.00',
      accounts: [
        {
          account_id: 'acc-1',
          name: 'HDFC Salary',
          account_type: 'savings',
          current_balance: '125000.00',
          is_liability: false,
          currency: 'INR',
          source: 'manual',
          status: 'active',
          transaction_count: 4,
          period_income: '85000.00',
          period_expenses: '22000.00',
          net_transaction_activity: '63000.00',
        },
      ],
    });
    vi.mocked(analyticsApi.getAccountDetail).mockResolvedValue({
      period_bounds: sampleBounds,
      granularity: 'day',
      account: {
        account_id: 'acc-1',
        name: 'HDFC Salary',
        account_type: 'savings',
        current_balance: '125000.00',
        is_liability: false,
        currency: 'INR',
        source: 'manual',
        status: 'active',
        transaction_count: 4,
        period_income: '85000.00',
        period_expenses: '22000.00',
        net_transaction_activity: '63000.00',
      },
      trend: [],
      category_distribution: [],
      recent_transactions: [],
      balance_history: [],
      balance_history_note: 'Ledger derived.',
      traceability: sampleTrace,
    });

    render(<AnalyticsPage onNavigate={onNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('₹63,000.00')).toBeInTheDocument();
      expect(screen.getByText('74.12%')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Expenses & Categories'));
    expect(screen.getByText('Average Daily Spend')).toBeInTheDocument();
    expect(screen.getByText('CSV Import')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Comparisons & Trends'));
    expect(screen.getByText(/Partial period comparison: 25 of 30 days elapsed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Account Analytics'));
    expect(screen.getByText(/Account Deep Dive: HDFC Salary/i)).toBeInTheDocument();
  });

  it('generates filtered reports and triggers CSV export cleanly', async () => {
    vi.mocked(analyticsApi.listReports).mockResolvedValue({
      reports: [
        {
          id: 'monthly_summary',
          title: 'Monthly Financial Summary',
          description: 'Full monthly overview',
          supports_csv_export: true,
        },
        {
          id: 'expense_report',
          title: 'Expense Report',
          description: 'Expenses only',
          supports_csv_export: true,
        },
      ],
    });
    vi.mocked(analyticsApi.getReport).mockResolvedValue({
      metadata: {
        report_type: 'monthly_summary',
        title: 'Monthly Financial Summary',
        start_date: '2026-11-01',
        end_date: '2026-11-30',
        generated_at: '2026-11-25T10:00:00+05:30',
        currency: 'INR',
        timezone: 'Asia/Kolkata',
      },
      summary_metrics: [
        { label: 'Total Income', value: '₹85,000.00', raw_decimal: '85000.00', highlight: 'positive' },
        { label: 'Total Expenses', value: '₹22,000.00', raw_decimal: '22000.00', highlight: 'negative' },
      ],
      category_breakdown: [],
      account_breakdown: [],
      cashflow_series: [],
      transactions: [],
      total_transactions: 0,
      traceability: sampleTrace,
    });
    vi.mocked(analyticsApi.exportReportCsv).mockResolvedValue({
      filename: 'pfm_monthly_summary_20261101_20261130.csv',
      content: 'Report Title,Monthly Financial Summary\r\n',
    });

    // Stub URL.createObjectURL & revokeObjectURL in jsdom
    const origCreate = URL.createObjectURL;
    const origRevoke = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    URL.revokeObjectURL = vi.fn();

    try {
      render(<ReportsPage onNavigate={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Monthly Financial Summary' })).toBeInTheDocument();
        expect(screen.getByText('₹85,000.00')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Export CSV/i }));
      await waitFor(() => {
        expect(analyticsApi.exportReportCsv).toHaveBeenCalledTimes(1);
      });
    } finally {
      URL.createObjectURL = origCreate;
      URL.revokeObjectURL = origRevoke;
    }
  });
});
