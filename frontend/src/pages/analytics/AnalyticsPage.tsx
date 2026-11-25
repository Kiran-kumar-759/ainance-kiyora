import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  BarChart3,
  CreditCard,
  Info,
  RefreshCw,
  Wallet,
} from 'lucide-react';
import { analyticsApi } from '../../services/analyticsApi';
import { financeApi } from '../../services/financeApi';
import { FinancialAccount } from '../../types/finance';
import {
  AccountAnalyticsDetailResponse,
  AccountAnalyticsListResponse,
  CashFlowAnalyticsResponse,
  CategoryAnalyticsResponse,
  ExpenseAnalyticsResponse,
  IncomeAnalyticsResponse,
  PeriodComparisonResponse,
  TransactionNavigationFilters,
  TrendAnalyticsResponse,
} from '../../types/analytics';
import { formatDate, formatINR } from '../../lib/formatters';
import {
  AccountBalanceDistributionChart,
  CategoryDonutChart,
  HorizontalCategoryBarChart,
  IncomeVsExpenseBarChart,
  PeriodComparisonBarChart,
  TrendLineChart,
} from '../../components/charts/FinanceCharts';
import { ComparisonBadge, PeriodFilterBar } from '../../components/analytics/PeriodFilterBar';

interface AnalyticsPageProps {
  onNavigate: (view: string, txFilters?: TransactionNavigationFilters) => void;
}

type AnalyticsTab = 'cashflow' | 'expenses' | 'income' | 'comparisons' | 'accounts';

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('cashflow');
  const [period, setPeriod] = useState<string>('this_month');
  const [customStart, setCustomStart] = useState<string>('');
  const [customEnd, setCustomEnd] = useState<string>('');
  const [granularity, setGranularity] = useState<string>('');
  const [accountId, setAccountId] = useState<string>('');
  const [comparisonPreset, setComparisonPreset] = useState<string>('month_over_month');
  const [dateError, setDateError] = useState<string | null>(null);

  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [cashflowData, setCashflowData] = useState<CashFlowAnalyticsResponse | null>(null);
  const [expenseData, setExpenseData] = useState<ExpenseAnalyticsResponse | null>(null);
  const [incomeData, setIncomeData] = useState<IncomeAnalyticsResponse | null>(null);
  const [categoryData, setCategoryData] = useState<CategoryAnalyticsResponse | null>(null);
  const [trendData, setTrendData] = useState<TrendAnalyticsResponse | null>(null);
  const [comparisonData, setComparisonData] = useState<PeriodComparisonResponse | null>(null);
  const [accountsAnalytics, setAccountsAnalytics] = useState<AccountAnalyticsListResponse | null>(
    null
  );
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [accountDetail, setAccountDetail] = useState<AccountAnalyticsDetailResponse | null>(null);

  useEffect(() => {
    financeApi
      .listAccounts(false)
      .then((accs) => setAccounts(accs))
      .catch(() => {});
  }, []);

  const fetchAnalytics = async () => {
    if (period === 'custom') {
      if (!customStart || !customEnd) return;
      if (customStart > customEnd) {
        setDateError('Start date cannot be after end date.');
        return;
      }
      setDateError(null);
    }

    setIsLoading(true);
    setError(null);

    const commonParams = {
      period,
      start_date: period === 'custom' ? customStart : undefined,
      end_date: period === 'custom' ? customEnd : undefined,
      granularity: granularity || undefined,
      account_id: accountId || undefined,
    };

    try {
      const [cf, exp, inc, cats, trnd, comp, accList] = await Promise.all([
        analyticsApi.getCashFlow(commonParams),
        analyticsApi.getExpenses(commonParams),
        analyticsApi.getIncome(commonParams),
        analyticsApi.getCategories({ ...commonParams, category_type: 'expense' }),
        analyticsApi.getTrends(commonParams),
        analyticsApi.getComparisons({
          comparison_preset: period === 'custom' ? 'custom' : comparisonPreset,
          start_date: period === 'custom' ? customStart : undefined,
          end_date: period === 'custom' ? customEnd : undefined,
          account_id: accountId || undefined,
        }),
        analyticsApi.getAccounts(commonParams),
      ]);

      setCashflowData(cf);
      setExpenseData(exp);
      setIncomeData(inc);
      setCategoryData(cats);
      setTrendData(trnd);
      setComparisonData(comp);
      setAccountsAnalytics(accList);

      const targetAcc = selectedAccountId || accList.accounts[0]?.account_id || '';
      if (targetAcc) {
        setSelectedAccountId(targetAcc);
        const detail = await analyticsApi.getAccountDetail(targetAcc, commonParams);
        setAccountDetail(detail);
      } else {
        setAccountDetail(null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load financial analytics.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (period !== 'custom') {
      fetchAnalytics();
    }
  }, [period, granularity, accountId, comparisonPreset]);

  const handleInspectAccount = async (accId: string) => {
    setSelectedAccountId(accId);
    try {
      const detail = await analyticsApi.getAccountDetail(accId, {
        period,
        start_date: period === 'custom' ? customStart : undefined,
        end_date: period === 'custom' ? customEnd : undefined,
        granularity: granularity || undefined,
      });
      setAccountDetail(detail);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load account analytics.');
    }
  };

  const drillToCategory = (
    categoryId: string | null | undefined,
    txType: 'income' | 'expense' = 'expense'
  ) => {
    const bounds = cashflowData?.period_bounds;
    onNavigate('transactions', {
      categoryId: categoryId || undefined,
      accountId: accountId || undefined,
      transactionType: txType,
      startDate: bounds?.start_date,
      endDate: bounds?.end_date,
    });
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
            <BarChart3 className="w-6 h-6 text-blue-600" />
            <span>Financial Analytics</span>
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Deterministic period breakdowns, category intelligence, cash flow, and historical comparisons.
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
            onApplyCustom={fetchAnalytics}
            dateError={dateError}
          />

          <select
            aria-label="Grouping Interval"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
            className="px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg bg-white font-medium text-gray-700"
          >
            <option value="">Auto Interval</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="quarterly">Quarterly</option>
          </select>

          <select
            aria-label="Filter by Account"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg bg-white font-medium text-gray-700"
          >
            <option value="">All Active Accounts</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={fetchAnalytics}
            disabled={isLoading}
            className="p-2 bg-white border border-gray-200 rounded-lg text-gray-500 hover:text-gray-800"
            title="Refresh Analytics"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-center space-x-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={fetchAnalytics} className="underline font-medium">
            Retry
          </button>
        </div>
      )}

      {/* Analytics Tabs */}
      <div className="border-b border-gray-200 flex flex-wrap gap-1">
        {[
          { id: 'cashflow', label: 'Cash Flow' },
          { id: 'expenses', label: 'Expenses & Categories' },
          { id: 'income', label: 'Income Analytics' },
          { id: 'comparisons', label: 'Comparisons & Trends' },
          { id: 'accounts', label: 'Account Analytics' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id as AnalyticsTab)}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Cash Flow */}
      {activeTab === 'cashflow' && cashflowData && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Total Income</div>
              <div className="text-xl font-bold text-emerald-700 mt-1">
                {formatINR(cashflowData.total_income)}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Total Expenses</div>
              <div className="text-xl font-bold text-rose-700 mt-1">
                {formatINR(cashflowData.total_expenses)}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Net Cash Flow</div>
              <div className="text-xl font-bold text-blue-900 mt-1">
                {formatINR(cashflowData.net_cash_flow)}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Savings Rate</div>
              <div className="text-xl font-bold text-gray-900 mt-1">
                {cashflowData.savings_rate_pct !== null && cashflowData.savings_rate_pct !== undefined
                  ? `${cashflowData.savings_rate_pct}%`
                  : 'N/A (Zero Income)'}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">
                Income vs Expenses ({cashflowData.granularity} grouping)
              </h2>
              <IncomeVsExpenseBarChart
                series={cashflowData.series}
                periodLabel={cashflowData.period_bounds.label}
              />
            </div>

            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">Net Savings Trajectory</h2>
              <TrendLineChart
                series={cashflowData.series}
                metric="net_savings"
                color="#2563eb"
                label="Net Cash Flow (INR)"
              />
            </div>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 flex items-start space-x-2">
            <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <strong>Calculation Traceability:</strong> {cashflowData.traceability.formula} •
              Included transactions: <strong>{cashflowData.traceability.included_transaction_count}</strong> •
              Excluded transfers: <strong>{cashflowData.traceability.excluded_transfer_count}</strong> •
              Excluded reversed journals: <strong>{cashflowData.traceability.excluded_reversed_count}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Expenses & Categories */}
      {activeTab === 'expenses' && expenseData && categoryData && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Total Expenses</div>
              <div className="text-xl font-bold text-rose-700 mt-1">
                {formatINR(expenseData.total_expenses)}
              </div>
              <div className="mt-1">
                <ComparisonBadge comparison={expenseData.comparison} invertGood />
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Average Daily Spend</div>
              <div className="text-xl font-bold text-gray-900 mt-1">
                {formatINR(expenseData.average_daily_spend)}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Average Monthly Spend</div>
              <div className="text-xl font-bold text-gray-900 mt-1">
                {expenseData.average_monthly_spend
                  ? formatINR(expenseData.average_monthly_spend)
                  : 'N/A (< 28 days)'}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Expense Transactions</div>
              <div className="text-xl font-bold text-gray-900 mt-1">
                {expenseData.transaction_count}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">
                Category Distribution (Click to Drill Down)
              </h2>
              <CategoryDonutChart
                items={categoryData.items}
                totalAmount={categoryData.total_amount}
                onSelectCategory={(id) => drillToCategory(id, 'expense')}
              />
            </div>

            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">Top Spending Categories</h2>
              <HorizontalCategoryBarChart
                items={categoryData.items}
                onSelectCategory={(id) => drillToCategory(id, 'expense')}
              />
            </div>
          </div>

          {/* Largest Individual Expenses & Source Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">Largest Individual Expenses</h2>
              {expenseData.largest_expenses.length === 0 ? (
                <p className="text-xs text-gray-500 py-4">No expense transactions in this period.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-gray-100 text-gray-500">
                      <tr>
                        <th className="py-2">Date</th>
                        <th className="py-2">Description</th>
                        <th className="py-2">Category</th>
                        <th className="py-2">Account</th>
                        <th className="py-2 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {expenseData.largest_expenses.map((tx) => (
                        <tr key={tx.id}>
                          <td className="py-2 text-gray-500 whitespace-nowrap">
                            {formatDate(tx.transaction_date)}
                          </td>
                          <td className="py-2 font-medium text-gray-900">{tx.description}</td>
                          <td className="py-2">{tx.category_name || 'Uncategorized'}</td>
                          <td className="py-2 text-gray-600">{tx.account_name}</td>
                          <td className="py-2 text-right font-bold text-rose-700 whitespace-nowrap">
                            {formatINR(tx.amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-4">
              <h2 className="text-sm font-bold text-gray-900">Expenses by Source</h2>
              {expenseData.by_source.length === 0 ? (
                <p className="text-xs text-gray-500">No source records.</p>
              ) : (
                <div className="space-y-2.5 text-xs">
                  {expenseData.by_source.map((s) => (
                    <div key={s.source} className="flex justify-between items-center p-2 bg-gray-50 rounded-lg">
                      <div>
                        <div className="font-semibold text-gray-800">{s.label}</div>
                        <div className="text-[11px] text-gray-500">{s.transaction_count} transactions</div>
                      </div>
                      <div className="text-right font-bold text-gray-900">
                        {formatINR(s.total_amount)} ({s.percentage}%)
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Income Analytics */}
      {activeTab === 'income' && incomeData && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Total Income</div>
              <div className="text-2xl font-bold text-emerald-700 mt-1">
                {formatINR(incomeData.total_income)}
              </div>
              <div className="mt-1">
                <ComparisonBadge comparison={incomeData.comparison} />
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Income Transactions</div>
              <div className="text-2xl font-bold text-gray-900 mt-1">
                {incomeData.transaction_count}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
              <div className="text-xs font-semibold text-gray-500">Top Income Source</div>
              <div className="text-base font-bold text-gray-900 mt-1">
                {incomeData.by_category[0]?.category_name || 'N/A'}
              </div>
              {incomeData.by_category[0] && (
                <div className="text-xs text-emerald-700 font-semibold">
                  {formatINR(incomeData.by_category[0].total_amount)} (
                  {incomeData.by_category[0].percentage}%)
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">Income Trend</h2>
              <TrendLineChart
                series={incomeData.trend}
                metric="income"
                color="#10b981"
                label="Income Progression (INR)"
              />
            </div>

            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">
                Income by Category (Click to Drill Down)
              </h2>
              <HorizontalCategoryBarChart
                items={incomeData.by_category}
                onSelectCategory={(id) => drillToCategory(id, 'income')}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">Income by Account</h2>
              {incomeData.by_account.length === 0 ? (
                <p className="text-xs text-gray-500">No income inflows in selected period.</p>
              ) : (
                <div className="space-y-2 text-xs">
                  {incomeData.by_account.map((a) => (
                    <div key={a.account_id} className="flex justify-between p-2.5 bg-gray-50 rounded-lg">
                      <span className="font-semibold text-gray-800">
                        {a.account_name} ({a.transaction_count} txns)
                      </span>
                      <span className="font-bold text-emerald-700">
                        {formatINR(a.total_amount)} ({a.percentage}%)
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">Income Source Distribution</h2>
              {incomeData.by_source.length === 0 ? (
                <p className="text-xs text-gray-500">No source records.</p>
              ) : (
                <div className="space-y-2 text-xs">
                  {incomeData.by_source.map((s) => (
                    <div key={s.source} className="flex justify-between p-2.5 bg-gray-50 rounded-lg">
                      <span className="font-semibold text-gray-800">
                        {s.label} ({s.transaction_count})
                      </span>
                      <span className="font-bold text-gray-900">
                        {formatINR(s.total_amount)} ({s.percentage}%)
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Comparisons & Historical Trends */}
      {activeTab === 'comparisons' && comparisonData && trendData && (
        <div className="space-y-6">
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold text-gray-900">Period Comparison Engine</h2>
              <p className="text-xs text-gray-500">
                Comparing <strong>{comparisonData.current_period.label}</strong> vs{' '}
                <strong>{comparisonData.previous_period.label}</strong>
              </p>
            </div>
            <select
              aria-label="Comparison Preset"
              value={comparisonPreset}
              onChange={(e) => setComparisonPreset(e.target.value)}
              className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg bg-white font-medium"
            >
              <option value="month_over_month">This Month vs Last Month</option>
              <option value="quarter_over_quarter">This Quarter vs Previous Quarter</option>
              <option value="year_over_year">This Year vs Previous Year</option>
              <option value="last_3_months">Last 3 Months vs Preceding 3 Months</option>
            </select>
          </div>

          {comparisonData.partial_period_warning && (
            <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <span>{comparisonData.partial_period_warning}</span>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h3 className="text-sm font-bold text-gray-900 mb-3">Period Comparison Chart</h3>
              <PeriodComparisonBarChart
                currentLabel={comparisonData.current_period.label}
                previousLabel={comparisonData.previous_period.label}
                income={comparisonData.income}
                expenses={comparisonData.expenses}
                netSavings={comparisonData.net_savings}
              />
            </div>

            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-3">
              <h3 className="text-sm font-bold text-gray-900">Ledger-Reconstructed Balance History</h3>
              <p className="text-[11px] text-gray-500">{trendData.balance_history_note}</p>
              {!trendData.balance_history_available ? (
                <p className="text-xs text-gray-500 py-6 text-center border border-dashed border-gray-200 rounded-lg">
                  No ledger history recorded in this date window.
                </p>
              ) : (
                <div className="overflow-x-auto max-h-60 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 sticky top-0">
                      <tr>
                        <th className="py-2 px-2">Date</th>
                        <th className="py-2 px-2 text-right">Assets</th>
                        <th className="py-2 px-2 text-right">Liabilities</th>
                        <th className="py-2 px-2 text-right">Net Position</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {trendData.balance_history.map((b) => (
                        <tr key={b.date}>
                          <td className="py-1.5 px-2 text-gray-600">{formatDate(b.date)}</td>
                          <td className="py-1.5 px-2 text-right text-emerald-700 font-medium">
                            {formatINR(b.assets_balance)}
                          </td>
                          <td className="py-1.5 px-2 text-right text-rose-700 font-medium">
                            {formatINR(b.liabilities_balance)}
                          </td>
                          <td className="py-1.5 px-2 text-right font-bold text-gray-900">
                            {formatINR(b.net_position)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Category-by-Category Comparison Table */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 mb-3">
              Category Spending Shifts ({comparisonData.current_period.label} vs{' '}
              {comparisonData.previous_period.label})
            </h3>
            {comparisonData.category_comparisons.length === 0 ? (
              <p className="text-xs text-gray-500">No spending categories recorded in either period.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-gray-200 text-gray-500 uppercase text-[10px]">
                    <tr>
                      <th className="py-2">Category</th>
                      <th className="py-2 text-right">Current</th>
                      <th className="py-2 text-right">Previous</th>
                      <th className="py-2 text-right">Difference</th>
                      <th className="py-2 text-right">Change</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {comparisonData.category_comparisons.map((c, idx) => (
                      <tr key={`${c.category_id || 'uncat'}-${idx}`}>
                        <td className="py-2 font-semibold text-gray-800">{c.category_name}</td>
                        <td className="py-2 text-right font-bold text-gray-900">
                          {formatINR(c.comparison.current_value)}
                        </td>
                        <td className="py-2 text-right text-gray-600">
                          {formatINR(c.comparison.previous_value)}
                        </td>
                        <td className="py-2 text-right font-medium">
                          {formatINR(c.comparison.absolute_difference)}
                        </td>
                        <td className="py-2 text-right">
                          <ComparisonBadge comparison={c.comparison} invertGood />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 5: Account-Wise Analytics */}
      {activeTab === 'accounts' && accountsAnalytics && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900 mb-3">
                Account Balance Distribution (Assets vs Credit Card Debt)
              </h2>
              <AccountBalanceDistributionChart accounts={accountsAnalytics.accounts} />
            </div>

            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
              <h2 className="text-sm font-bold text-gray-900 mb-3">Active Account Activity</h2>
              {accountsAnalytics.accounts.length === 0 ? (
                <p className="text-xs text-gray-500">No active accounts.</p>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-gray-200 text-gray-500 uppercase text-[10px]">
                    <tr>
                      <th className="py-2">Account</th>
                      <th className="py-2 text-right">Balance</th>
                      <th className="py-2 text-right">Income</th>
                      <th className="py-2 text-right">Expenses</th>
                      <th className="py-2 text-right">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {accountsAnalytics.accounts.map((acc) => (
                      <tr key={acc.account_id} className="hover:bg-gray-50">
                        <td className="py-2.5">
                          <div className="font-semibold text-gray-900 flex items-center space-x-1.5">
                            {acc.is_liability ? (
                              <CreditCard className="w-3.5 h-3.5 text-rose-500" />
                            ) : (
                              <Wallet className="w-3.5 h-3.5 text-emerald-500" />
                            )}
                            <span>{acc.name}</span>
                          </div>
                          <div className="text-[10px] text-gray-500">
                            {acc.account_type.replace('_', ' ').toUpperCase()} •{' '}
                            {acc.transaction_count} txns
                          </div>
                        </td>
                        <td
                          className={`py-2.5 text-right font-bold ${
                            acc.is_liability ? 'text-rose-700' : 'text-gray-900'
                          }`}
                        >
                          {acc.is_liability ? '-' : ''}
                          {formatINR(acc.current_balance)}
                        </td>
                        <td className="py-2.5 text-right text-emerald-700 font-medium">
                          +{formatINR(acc.period_income)}
                        </td>
                        <td className="py-2.5 text-right text-rose-700 font-medium">
                          -{formatINR(acc.period_expenses)}
                        </td>
                        <td className="py-2.5 text-right">
                          <button
                            type="button"
                            onClick={() => handleInspectAccount(acc.account_id)}
                            className={`px-2 py-1 rounded text-[11px] font-semibold ${
                              selectedAccountId === acc.account_id
                                ? 'bg-blue-600 text-white'
                                : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                            }`}
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {accountDetail && (
            <div className="bg-white p-5 rounded-xl border border-blue-200 shadow-sm space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-gray-100">
                <div>
                  <h3 className="text-base font-bold text-gray-900">
                    Account Deep Dive: {accountDetail.account.name}
                  </h3>
                  <p className="text-xs text-gray-500">
                    {accountDetail.account.institution_name || 'Manual Account'} • Current{' '}
                    {accountDetail.account.is_liability ? 'Outstanding Liability' : 'Balance'}:{' '}
                    <strong>{formatINR(accountDetail.account.current_balance)}</strong>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    onNavigate('transactions', { accountId: accountDetail.account.account_id })
                  }
                  className="text-xs text-blue-600 hover:underline font-semibold"
                >
                  View Account Transactions &rarr;
                </button>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <IncomeVsExpenseBarChart
                  series={accountDetail.trend}
                  periodLabel={accountDetail.period_bounds.label}
                />
                <HorizontalCategoryBarChart
                  items={accountDetail.category_distribution}
                  onSelectCategory={(catId) =>
                    onNavigate('transactions', {
                      accountId: accountDetail.account.account_id,
                      categoryId: catId || undefined,
                      transactionType: 'expense',
                    })
                  }
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
