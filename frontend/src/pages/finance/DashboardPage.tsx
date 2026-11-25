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
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import { FinancialDashboard } from '../../types/finance';
import { formatINR, formatDate } from '../../lib/formatters';

interface DashboardPageProps {
  onNavigate: (view: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const [period, setPeriod] = useState<string>('this_month');
  const [data, setData] = useState<FinancialDashboard | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = async (selectedPeriod: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await financeApi.getDashboard(selectedPeriod);
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load financial dashboard.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard(period);
  }, [period]);

  return (
    <div className="space-y-6">
      {/* Header with Title and Period Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Financial Overview</h1>
          <p className="text-sm text-gray-600 mt-1">
            Real-time balance positions, income, expenses, and ledger summary.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1 shadow-sm">
            {[
              { id: 'this_month', label: 'This Month' },
              { id: 'last_month', label: 'Last Month' },
              { id: 'this_year', label: 'This Year' },
              { id: 'all_time', label: 'All Time' },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => setPeriod(p.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  period === p.id
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <button
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
            onClick={() => fetchDashboard(period)}
            className="underline text-red-800 hover:text-red-900 font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Net Financial Position */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow transition-shadow">
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

        {/* Total Assets */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow transition-shadow">
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
            <p className="text-xs text-gray-500 mt-1">Savings, Current, Cash & Digital Wallets</p>
          </div>
        </div>

        {/* Credit Card Liabilities */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow transition-shadow">
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
            <p className="text-xs text-gray-500 mt-1">Total outstanding credit card balance</p>
          </div>
        </div>

        {/* Total Accounts */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow transition-shadow">
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
            <div className="flex items-center space-x-1 mt-1">
              <button
                onClick={() => onNavigate('accounts')}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium"
              >
                Manage Accounts &rarr;
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Period Income vs Expenses Strip */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-gray-100 gap-2">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Period Cash Flow</h2>
            <p className="text-xs text-gray-500">
              {data?.period_start ? formatDate(data.period_start) : ''} to{' '}
              {data?.period_end ? formatDate(data.period_end) : ''}
            </p>
          </div>
          {data?.savings_rate_pct !== null && data?.savings_rate_pct !== undefined && (
            <div className="inline-flex items-center space-x-1 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Savings Rate: {data.savings_rate_pct}%</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-4">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs text-gray-500 font-medium">Total Income</span>
              <div className="text-xl font-bold text-emerald-700 mt-0.5">
                {isLoading ? '...' : formatINR(data?.total_income)}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center flex-shrink-0">
              <TrendingDown className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs text-gray-500 font-medium">Total Expenses</span>
              <div className="text-xl font-bold text-rose-700 mt-0.5">
                {isLoading ? '...' : formatINR(data?.total_expenses)}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0">
              <ArrowRightLeft className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs text-gray-500 font-medium">Net Savings</span>
              <div className="text-xl font-bold text-blue-900 mt-0.5">
                {isLoading ? '...' : formatINR(data?.net_savings)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions Bar */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={() => onNavigate('transactions')}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Add Transaction</span>
        </button>

        <button
          onClick={() => onNavigate('transfers')}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 rounded-lg text-sm font-medium shadow-sm transition-colors"
        >
          <ArrowRightLeft className="w-4 h-4 text-blue-600" />
          <span>Transfer Money</span>
        </button>

        <button
          onClick={() => onNavigate('accounts')}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 rounded-lg text-sm font-medium shadow-sm transition-colors"
        >
          <Wallet className="w-4 h-4 text-emerald-600" />
          <span>Add Account</span>
        </button>

        <button
          onClick={() => onNavigate('imports')}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 rounded-lg text-sm font-medium shadow-sm transition-colors"
        >
          <Landmark className="w-4 h-4 text-purple-600" />
          <span>Import Statement</span>
        </button>

        <button
          onClick={() => onNavigate('banking')}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-sm font-medium transition-colors"
        >
          <Landmark className="w-4 h-4 text-indigo-600" />
          <span>Simulated Bank Connection</span>
        </button>
      </div>

      {/* Accounts & Recent Transactions Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Accounts Overview (1 col) */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">Your Accounts</h2>
            <button
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
                  onClick={() => onNavigate('accounts')}
                  className="mt-2 text-xs text-blue-600 hover:underline font-semibold"
                >
                  + Create Your First Account
                </button>
              </div>
            ) : (
              data?.accounts.slice(0, 5).map((acc) => (
                <div
                  key={acc.id}
                  className="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center space-x-3">
                    <div
                      className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                        acc.account_type === 'credit_card'
                          ? 'bg-rose-50 text-rose-600'
                          : 'bg-blue-50 text-blue-600'
                      }`}
                    >
                      {acc.account_type === 'credit_card' ? (
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
                        {acc.source === 'demo_bank' && (
                          <span className="px-1.5 py-0.2 bg-purple-50 text-purple-700 text-[10px] font-semibold rounded border border-purple-200">
                            Demo
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className={`text-sm font-bold ${
                        acc.account_type === 'credit_card' ? 'text-rose-600' : 'text-gray-900'
                      }`}
                    >
                      {formatINR(acc.current_balance)}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Transactions Table (2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">Recent Transactions</h2>
            <button
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
                <div className="mt-3 flex justify-center space-x-3">
                  <button
                    onClick={() => onNavigate('transactions')}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700"
                  >
                    + Record Transaction
                  </button>
                  <button
                    onClick={() => onNavigate('imports')}
                    className="px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-medium hover:bg-indigo-100"
                  >
                    Upload Bank Statement
                  </button>
                  <button
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
