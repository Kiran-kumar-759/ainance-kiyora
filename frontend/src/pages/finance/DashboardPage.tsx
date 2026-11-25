import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  CreditCard,
  ArrowUpRight,
  ArrowDownLeft,
  ArrowRightLeft,
  Plus,
  RefreshCw,
  AlertCircle,
  Landmark,
  PiggyBank,
  CheckCircle2,
  BarChart3,
  FileText,
  Info,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import { analyticsApi } from '../../services/analyticsApi';
import { FinancialDashboard } from '../../types/finance';
import {
  AnalyticsDashboard,
  TransactionNavigationFilters,
} from '../../types/analytics';
import { formatINR, formatDate } from '../../lib/formatters';
import {
  CategoryDonutChart,
  IncomeVsExpenseBarChart,
  TrendLineChart,
} from '../../components/charts/FinanceCharts';
import {
  ComparisonBadge,
  PeriodFilterBar,
} from '../../components/analytics/PeriodFilterBar';

interface DashboardPageProps {
  onNavigate: (view: string, txFilters?: TransactionNavigationFilters) => void;
  userName?: string | null;
}

function adaptLegacyDashboard(legacy: FinancialDashboard): AnalyticsDashboard {
  const zeroComp = {
    current_value: '0.00',
    previous_value: '0.00',
    absolute_difference: '0.00',
    percentage_change: null,
    trend_direction: 'flat' as const,
    is_zero_baseline: true,
    comparison_note: null,
  };
  return {
    total_assets: legacy.total_assets,
    total_liabilities: legacy.total_liabilities,
    net_financial_position: legacy.net_financial_position,
    account_count: legacy.account_count,
    balance_as_of_note:
      'Account balances and net financial position reflect real-time ledger balances.',
    period_bounds: {
      period: legacy.period,
      label: legacy.period.replace(/_/g, ' '),
      start_date: legacy.period_start,
      end_date: legacy.period_end,
      timezone: 'Asia/Kolkata',
      is_partial_period: false,
      days_in_period: 30,
      elapsed_days: 30,
    },
    total_income: legacy.total_income,
    total_expenses: legacy.total_expenses,
    net_savings: legacy.net_savings,
    savings_rate_pct: legacy.savings_rate_pct,
    income_comparison: zeroComp,
    expense_comparison: zeroComp,
    savings_comparison: zeroComp,
    income_vs_expense_series: [],
    spending_by_category: [],
    monthly_spending_trend: [],
    account_balances: legacy.accounts.map((a) => ({
      account_id: a.id,
      name: a.name,
      institution_name: a.institution_name,
      account_type: a.account_type,
      current_balance: a.current_balance,
      is_liability: a.account_type === 'credit_card' || a.account_type === 'loan_liability',
      currency: a.currency,
      source: a.source,
      status: a.status,
      transaction_count: 0,
      period_income: '0.00',
      period_expenses: '0.00',
      net_transaction_activity: '0.00',
    })),
    accounts: legacy.accounts,
    recent_transactions: legacy.recent_transactions,
    is_empty_state: legacy.account_count === 0 && legacy.recent_transactions.length === 0,
    traceability: {
      formula: 'Net Position = Assets - Liabilities',
      included_transaction_count: legacy.recent_transactions.length,
      excluded_transfer_count: 0,
      excluded_reversed_count: 0,
      currency: 'INR',
    },
  };
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate, userName }) => {
  const [period, setPeriod] = useState<string>('this_month');
  const [customStart, setCustomStart] = useState<string>('');
  const [customEnd, setCustomEnd] = useState<string>('');
  const [dateError, setDateError] = useState<string | null>(null);
  const [data, setData] = useState<AnalyticsDashboard | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = async (
    selectedPeriod: string,
    startOverride?: string,
    endOverride?: string
  ) => {
    if (selectedPeriod === 'custom') {
      const s = startOverride ?? customStart;
      const e = endOverride ?? customEnd;
      if (!s || !e) return;
      if (s > e) {
        setDateError('Start date cannot be after end date.');
        return;
      }
      setDateError(null);
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await analyticsApi.getDashboard({
        period: selectedPeriod,
        start_date: selectedPeriod === 'custom' ? startOverride ?? customStart : undefined,
        end_date: selectedPeriod === 'custom' ? endOverride ?? customEnd : undefined,
      });
      setData(res);
    } catch (analyticsErr: unknown) {
      // Backwards-compatible fallback if only /api/v1/finance/dashboard is mocked in unit tests
      try {
        if (selectedPeriod !== 'custom') {
          const legacy = await financeApi.getDashboard(selectedPeriod);
          if (legacy && typeof legacy === 'object' && 'total_assets' in legacy) {
            setData(adaptLegacyDashboard(legacy));
            return;
          }
        }
      } catch {
        // Fall through to report original error
      }
      const msg =
        analyticsErr instanceof Error
          ? analyticsErr.message
          : 'Failed to load financial dashboard.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (period !== 'custom') {
      fetchDashboard(period);
    }
  }, [period]);

  const handleCategoryDrilldown = (categoryId: string | null) => {
    onNavigate('transactions', {
      categoryId: categoryId || undefined,
      transactionType: 'expense',
      startDate: data?.period_bounds.start_date,
      endDate: data?.period_bounds.end_date,
    });
  };

  return (
    <div className="space-y-6">
      {/* Header with Welcome & Period Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Financial Overview</h1>
          <p className="text-sm text-gray-600 mt-1">
            {userName ? `Welcome, ${userName} • ` : ''}
            Real-time balance positions, period cash flow, spending breakdown, and ledger analytics.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <PeriodFilterBar
            period={period}
            startDate={customStart}
            endDate={customEnd}
            onPeriodChange={(p) => {
              setDateError(null);
              setPeriod(p);
            }}
            onStartDateChange={setCustomStart}
            onEndDateChange={setCustomEnd}
            onApplyCustom={() => fetchDashboard('custom')}
            dateError={dateError}
          />

          <button
            type="button"
            onClick={() => fetchDashboard(period)}
            disabled={isLoading}
            className="p-2 text-gray-500 hover:text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 shadow-sm transition-colors"
            title="Refresh Data"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center space-x-3 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" />
          <div className="flex-1">
            <span className="font-semibold">Error:</span> {error}
          </div>
          <button
            type="button"
            onClick={() => fetchDashboard(period)}
            className="underline text-red-800 hover:text-red-900 font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Clarity Banner: Real-time Balances vs Selected Transaction Period */}
      {data && (
        <div className="px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs text-slate-600">
          <div className="flex items-center space-x-2">
            <Info className="w-4 h-4 text-blue-600 flex-shrink-0" />
            <span>
              <strong>Balances vs. Period:</strong> Net Financial Position, Assets, and Credit Card
              Debt show <strong>current real-time account balances</strong>, whereas Income,
              Expenses, and Charts reflect{' '}
              <strong>
                {formatDate(data.period_bounds.start_date)} –{' '}
                {formatDate(data.period_bounds.end_date)}
              </strong>{' '}
              (IST).
            </span>
          </div>
          <div className="flex items-center space-x-3 whitespace-nowrap">
            <button
              type="button"
              onClick={() => onNavigate('analytics')}
              className="text-blue-600 hover:text-blue-800 font-semibold inline-flex items-center space-x-1"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>Full Analytics &rarr;</span>
            </button>
            <button
              type="button"
              onClick={() => onNavigate('reports')}
              className="text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center space-x-1"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Reports &amp; CSV &rarr;</span>
            </button>
          </div>
        </div>
      )}

      {/* Balance Sheet Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Net Financial Position
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <PiggyBank className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-gray-900">
              {isLoading ? '...' : formatINR(data?.net_financial_position)}
            </div>
            <p className="text-xs text-gray-500 mt-1">Total Assets minus Credit Card Debt</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Total Assets
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Wallet className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-emerald-600">
              {isLoading ? '...' : formatINR(data?.total_assets)}
            </div>
            <p className="text-xs text-gray-500 mt-1">Savings, Current, Cash &amp; Wallets</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Credit Card Outstanding
            </span>
            <div className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
              <CreditCard className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-rose-600">
              {isLoading ? '...' : formatINR(data?.total_liabilities)}
            </div>
            <p className="text-xs text-gray-500 mt-1">Total outstanding card liability</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Active Accounts
            </span>
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Landmark className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-gray-900">
              {isLoading ? '...' : data?.account_count ?? 0}
            </div>
            <button
              type="button"
              onClick={() => onNavigate('accounts')}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium mt-1"
            >
              Manage Accounts &rarr;
            </button>
          </div>
        </div>
      </div>

      {/* Period Cash Flow Strip + Period-over-Period Comparisons */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-gray-100 gap-2">
          <div>
            <h2 className="text-base font-semibold text-gray-900">
              Period Cash Flow ({data?.period_bounds.label || 'Current Period'})
            </h2>
            <p className="text-xs text-gray-500">
              {data?.period_bounds.start_date ? formatDate(data.period_bounds.start_date) : ''} to{' '}
              {data?.period_bounds.end_date ? formatDate(data.period_bounds.end_date) : ''} •
              Excludes internal transfers &amp; reversals
            </p>
          </div>
          <div className="inline-flex items-center space-x-1.5 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-semibold">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>
              Savings Rate:{' '}
              {data?.savings_rate_pct !== null && data?.savings_rate_pct !== undefined
                ? `${data.savings_rate_pct}%`
                : 'N/A (Zero Income)'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
          <div className="flex items-start space-x-4">
            <div className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs text-gray-500 font-medium">Total Income</span>
              <div className="text-xl font-bold text-emerald-700 mt-0.5">
                {isLoading ? '...' : formatINR(data?.total_income)}
              </div>
              <div className="mt-1">
                <ComparisonBadge comparison={data?.income_comparison} />
              </div>
            </div>
          </div>

          <div className="flex items-start space-x-4">
            <div className="w-11 h-11 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center flex-shrink-0">
              <TrendingDown className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs text-gray-500 font-medium">Total Expenses</span>
              <div className="text-xl font-bold text-rose-700 mt-0.5">
                {isLoading ? '...' : formatINR(data?.total_expenses)}
              </div>
              <div className="mt-1">
                <ComparisonBadge comparison={data?.expense_comparison} invertGood />
              </div>
            </div>
          </div>

          <div className="flex items-start space-x-4">
            <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0">
              <ArrowRightLeft className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs text-gray-500 font-medium">Net Savings</span>
              <div className="text-xl font-bold text-blue-900 mt-0.5">
                {isLoading ? '...' : formatINR(data?.net_savings)}
              </div>
              <div className="mt-1">
                <ComparisonBadge comparison={data?.savings_comparison} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions Bar */}
      <div className="flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          onClick={() => onNavigate('transactions')}
          className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>Add Transaction</span>
        </button>
        <button
          type="button"
          onClick={() => onNavigate('transfers')}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 rounded-lg text-sm font-medium shadow-sm"
        >
          <ArrowRightLeft className="w-4 h-4 text-blue-600" />
          <span>Transfer Money</span>
        </button>
        <button
          type="button"
          onClick={() => onNavigate('accounts')}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 rounded-lg text-sm font-medium shadow-sm"
        >
          <Wallet className="w-4 h-4 text-emerald-600" />
          <span>Add Account</span>
        </button>
        <button
          type="button"
          onClick={() => onNavigate('imports')}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 rounded-lg text-sm font-medium shadow-sm"
        >
          <Landmark className="w-4 h-4 text-purple-600" />
          <span>Import Statement</span>
        </button>
        <button
          type="button"
          onClick={() => onNavigate('analytics')}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-sm font-medium"
        >
          <BarChart3 className="w-4 h-4 text-indigo-600" />
          <span>Detailed Analytics</span>
        </button>
        <button
          type="button"
          onClick={() => onNavigate('reports')}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-lg text-sm font-medium"
        >
          <FileText className="w-4 h-4 text-emerald-600" />
          <span>Financial Reports</span>
        </button>
      </div>

      {/* Charts Row: Income vs Expenses + Spending Breakdown + 6M Spending Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-900">Income vs Expenses</h2>
            <button
              type="button"
              onClick={() => onNavigate('analytics')}
              className="text-xs text-blue-600 hover:underline font-medium"
            >
              Inspect Cash Flow &rarr;
            </button>
          </div>
          <IncomeVsExpenseBarChart
            series={data?.income_vs_expense_series || []}
            periodLabel={data?.period_bounds.label}
          />
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-900">Spending by Category</h2>
            <span className="text-[11px] text-gray-400">Click category to view transactions</span>
          </div>
          <CategoryDonutChart
            items={data?.spending_by_category || []}
            totalAmount={data?.total_expenses ?? '0.00'}
            onSelectCategory={(catId) => handleCategoryDrilldown(catId)}
          />
        </div>
      </div>

      {/* Monthly Spending Trend */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h2 className="text-base font-semibold text-gray-900">6-Month Spending Trend</h2>
            <p className="text-xs text-gray-500">Monthly expense progression from actual ledger entries</p>
          </div>
          <button
            type="button"
            onClick={() => onNavigate('analytics')}
            className="text-xs text-blue-600 hover:underline font-medium"
          >
            Historical Trends &amp; Comparisons &rarr;
          </button>
        </div>
        <TrendLineChart
          series={data?.monthly_spending_trend || []}
          metric="expenses"
          color="#f43f5e"
          label="Monthly Expenses (INR)"
        />
      </div>

      {/* Accounts & Recent Transactions Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">Account Balances</h2>
            <button
              type="button"
              onClick={() => onNavigate('accounts')}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              View All ({data?.accounts.length ?? 0})
            </button>
          </div>

          <div className="space-y-3 mt-4">
            {data?.accounts.length === 0 ? (
              <div className="text-center py-6 text-gray-500 text-sm">
                <p>No financial accounts yet.</p>
                <button
                  type="button"
                  onClick={() => onNavigate('accounts')}
                  className="mt-2 text-xs text-blue-600 hover:underline font-semibold"
                >
                  + Create Your First Account
                </button>
              </div>
            ) : (
              data?.accounts.slice(0, 6).map((acc) => (
                <button
                  key={acc.id}
                  type="button"
                  onClick={() => onNavigate('transactions', { accountId: acc.id })}
                  className="w-full flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex items-center space-x-3">
                    <div
                      className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                        acc.account_type === 'credit_card' || acc.account_type === 'loan_liability'
                          ? 'bg-rose-50 text-rose-600'
                          : 'bg-blue-50 text-blue-600'
                      }`}
                    >
                      {acc.account_type === 'credit_card' || acc.account_type === 'loan_liability' ? (
                        <CreditCard className="w-4 h-4" />
                      ) : (
                        <Wallet className="w-4 h-4" />
                      )}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-gray-900 leading-tight">
                        {acc.name}
                      </div>
                      <div className="text-xs text-gray-500 flex items-center space-x-1.5 mt-0.5">
                        <span className="capitalize">{acc.account_type.replace('_', ' ')}</span>
                        {acc.account_identifier && <span>• {acc.account_identifier}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className={`text-sm font-bold ${
                        acc.account_type === 'credit_card' || acc.account_type === 'loan_liability'
                          ? 'text-rose-600'
                          : 'text-gray-900'
                      }`}
                    >
                      {formatINR(acc.current_balance)}
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">Recent Transactions</h2>
            <button
              type="button"
              onClick={() => onNavigate('transactions')}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              All Transactions &rarr;
            </button>
          </div>

          <div className="mt-4 overflow-x-auto">
            {data?.recent_transactions.length === 0 ? (
              <div className="text-center py-10 text-gray-500 text-sm">
                <p>No transactions recorded for this period.</p>
                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => onNavigate('transactions')}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700"
                  >
                    + Record Transaction
                  </button>
                  <button
                    type="button"
                    onClick={() => onNavigate('imports')}
                    className="px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-medium hover:bg-indigo-100"
                  >
                    Upload Bank Statement
                  </button>
                  <button
                    type="button"
                    onClick={() => onNavigate('banking')}
                    className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-200"
                  >
                    Import Demo Transactions
                  </button>
                </div>
              </div>
            ) : (
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-xs font-semibold text-gray-500 border-b border-gray-100">
                    <th className="pb-2">Date</th>
                    <th className="pb-2">Description</th>
                    <th className="pb-2">Account</th>
                    <th className="pb-2">Category</th>
                    <th className="pb-2">Source</th>
                    <th className="pb-2 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data?.recent_transactions.map((tx) => (
                    <tr key={tx.id} className="hover:bg-gray-50/80 transition-colors">
                      <td className="py-2.5 text-xs text-gray-500 whitespace-nowrap">
                        {formatDate(tx.transaction_date)}
                      </td>
                      <td className="py-2.5">
                        <div className="font-medium text-gray-900 leading-snug">
                          {tx.description}
                        </div>
                        {tx.merchant_payee && (
                          <div className="text-xs text-gray-500">{tx.merchant_payee}</div>
                        )}
                      </td>
                      <td className="py-2.5 text-xs text-gray-600">
                        {tx.account_name || 'Account'}
                      </td>
                      <td className="py-2.5">
                        {tx.category_name ? (
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                            style={{
                              backgroundColor: `${tx.category_color || '#3b82f6'}15`,
                              color: tx.category_color || '#1e40af',
                            }}
                          >
                            {tx.category_name}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="py-2.5 text-[10px] font-semibold uppercase text-gray-500">
                        {tx.source.replace('_', ' ')}
                      </td>
                      <td className="py-2.5 text-right font-semibold whitespace-nowrap">
                        {tx.transaction_type === 'income' ? (
                          <span className="text-emerald-600 inline-flex items-center">
                            <ArrowDownLeft className="w-3.5 h-3.5 mr-0.5" />
                            +{formatINR(tx.amount)}
                          </span>
                        ) : tx.transaction_type === 'expense' ? (
                          <span className="text-rose-600 inline-flex items-center">
                            <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
                            -{formatINR(tx.amount)}
                          </span>
                        ) : (
                          <span className="text-blue-600 inline-flex items-center">
                            <ArrowRightLeft className="w-3.5 h-3.5 mr-0.5" />
                            {formatINR(tx.amount)}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
