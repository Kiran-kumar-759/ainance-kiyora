import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Bell,
  Calculator,
  Eye,
  Landmark,
  Plus,
  RefreshCw,
  Search,
  TrendingUp,
} from 'lucide-react';
import { loansApi } from '../../services/phase6Api';
import { financeApi } from '../../services/financeApi';
import { billsApi } from '../../services/billsApi';
import { FinancialAccount } from '../../types/finance';
import {
  CalculationMethod,
  EmiCalculatorResult,
  EmiFrequency,
  Loan,
  LoanAnalytics,
  LoanInstallment,
  LoanOverview,
  LoanPayment,
} from '../../types/phase6';
import { formatDate, formatINR } from '../../lib/formatters';
import {
  LOAN_TYPES,
  LoanDetailsModal,
  LoanFormModal,
  LoanPaymentModal,
} from './LoanModals';

interface LoansPageProps {
  onNavigate: (view: string) => void;
}

type LoanTab = 'loans' | 'payments' | 'calculator' | 'analytics';

export const LoansPage: React.FC<LoansPageProps> = ({ onNavigate }) => {
  const [tab, setTab] = useState<LoanTab>('loans');
  const [overview, setOverview] = useState<LoanOverview | null>(null);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [payments, setPayments] = useState<LoanPayment[]>([]);
  const [analytics, setAnalytics] = useState<LoanAnalytics | null>(null);
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);

  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('next_due_asc');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingLoan, setEditingLoan] = useState<Loan | null>(null);
  const [payingLoan, setPayingLoan] = useState<Loan | null>(null);
  const [payingInst, setPayingInst] = useState<LoanInstallment | null>(null);
  const [prepayPreset, setPrepayPreset] = useState<{
    principal: string;
    mode: 'reduce_tenure' | 'reduce_emi';
    fee: string;
  } | null>(null);
  const [detailsLoan, setDetailsLoan] = useState<Loan | null>(null);

  // EMI Calculator State
  const [calcPrincipal, setCalcPrincipal] = useState('500000');
  const [calcRate, setCalcRate] = useState('9.0');
  const [calcTenure, setCalcTenure] = useState('60');
  const [calcFreq, setCalcFreq] = useState<EmiFrequency>('monthly');
  const [calcMethod, setCalcMethod] = useState<CalculationMethod>('reducing_balance');
  const [calcResult, setCalcResult] = useState<EmiCalculatorResult | null>(null);
  const [calcLoading, setCalcLoading] = useState(false);

  useEffect(() => {
    financeApi.listAccounts(false).then(setAccounts).catch(() => {});
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, listRes, payRes, anaRes] = await Promise.all([
        loansApi.getOverview(),
        loansApi.listLoans({
          loan_type: typeFilter || undefined,
          status_filter: statusFilter || undefined,
          search: search.trim() || undefined,
          sort_by: sortBy,
          page: 1,
          page_size: 50,
        }),
        loansApi.listPayments(),
        loansApi.getAnalytics(),
      ]);
      setOverview(ov);
      setLoans(listRes.items);
      setPayments(payRes.items);
      setAnalytics(anaRes);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load loans.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, typeFilter, statusFilter, sortBy]);

  const handleCalculateEmi = async (e: React.FormEvent) => {
    e.preventDefault();
    setCalcLoading(true);
    setError(null);
    try {
      const res = await loansApi.calculateEmi({
        principal: Number(calcPrincipal).toFixed(2),
        annual_interest_rate: calcMethod === 'zero_interest' ? '0.000' : Number(calcRate).toFixed(3),
        tenure_installments: Number(calcTenure),
        emi_frequency: calcFreq,
        calculation_method: calcMethod,
      });
      setCalcResult(res);
    } catch (ex: unknown) {
      setError(ex instanceof Error ? ex.message : 'EMI calculation failed.');
    } finally {
      setCalcLoading(false);
    }
  };

  const handleRunReminders = async () => {
    try {
      const res = await billsApi.processReminders();
      setBanner(
        `Processed ${res.processed_count} due reminder(s), created ${res.notifications_created} notification(s).`
      );
      await loadData();
    } catch (ex: unknown) {
      setError(ex instanceof Error ? ex.message : 'Failed to process reminders.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Loans, EMIs &amp; Amortization
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Track existing or new loans with separated principal liability transfers and interest
            expenses in your ledger.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onNavigate('reminders')}
            className="inline-flex items-center space-x-1.5 px-3 py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-semibold transition-colors"
          >
            <span>Reminders &amp; Logs &rarr;</span>
          </button>
          <button
            type="button"
            onClick={handleRunReminders}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-sm"
          >
            <Bell className="w-4 h-4 text-indigo-600" />
            <span>Run EMI Reminders</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setEditingLoan(null);
              setFormOpen(true);
            }}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Add Loan</span>
          </button>
        </div>
      </div>

      {banner && (
        <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-xs text-indigo-900 flex justify-between">
          <span>{banner}</span>
          <button type="button" onClick={() => setBanner(null)} className="underline font-semibold">
            Dismiss
          </button>
        </div>
      )}

      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="bg-white rounded-xl border border-rose-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-rose-700">
              Outstanding Principal
            </div>
            <div className="text-2xl font-bold text-rose-700 mt-1">
              {formatINR(overview.total_outstanding_principal)}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              {overview.active_loans_count} active • {overview.closed_loans_count} closed
            </div>
          </div>

          <div className="bg-white rounded-xl border border-indigo-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-indigo-700">
              Monthly EMI Commitment
            </div>
            <div className="text-2xl font-bold text-indigo-700 mt-1">
              {formatINR(overview.total_monthly_emi_commitment)}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              {overview.overdue_installments_count} overdue EMI(s)
            </div>
          </div>

          <div className="bg-white rounded-xl border border-emerald-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-emerald-700">
              Principal Repaid
            </div>
            <div className="text-2xl font-bold text-emerald-700 mt-1">
              {formatINR(overview.total_principal_repaid)}
            </div>
            <div className="text-[11px] text-gray-500 mt-0.5">Reduces loan liability</div>
          </div>

          <div className="bg-white rounded-xl border border-amber-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-amber-700">
              Interest Paid
            </div>
            <div className="text-2xl font-bold text-amber-700 mt-1">
              {formatINR(overview.total_interest_paid)}
            </div>
            <div className="text-[11px] text-gray-500 mt-0.5">Recorded as expense</div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-gray-500">Next EMI Due</div>
            {overview.next_emi_due_loan ? (
              <>
                <div className="text-sm font-bold text-gray-900 mt-1 truncate">
                  {overview.next_emi_due_loan.loan_name}
                </div>
                <div className="text-xs text-gray-600 mt-0.5">
                  {overview.next_emi_due_loan.next_emi_due_date
                    ? formatDate(overview.next_emi_due_loan.next_emi_due_date)
                    : '—'}{' '}
                  • {formatINR(overview.next_emi_due_loan.emi_amount)}
                </div>
              </>
            ) : (
              <div className="text-xs text-gray-400 mt-2">No active EMIs pending</div>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={loadData} className="underline font-semibold">
            Retry
          </button>
        </div>
      )}

      <div className="border-b border-gray-200 flex flex-wrap gap-1">
        {[
          { id: 'loans', label: `My Loans (${loans.length})` },
          { id: 'payments', label: `Repayment History (${payments.length})` },
          { id: 'calculator', label: 'EMI Calculator' },
          { id: 'analytics', label: 'Loan Analytics' },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id as LoanTab)}
            className={`px-3.5 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
              tab === t.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'loans' && (
        <div className="space-y-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void loadData();
            }}
            className="bg-white p-3.5 rounded-xl border border-gray-200 flex flex-wrap items-center gap-2 text-xs"
          >
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search loan name, bank, ref..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 border border-gray-300 rounded-lg"
              />
            </div>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Loan Types</option>
              {LOAN_TYPES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="overdue">Overdue</option>
              <option value="closed">Closed</option>
            </select>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="next_due_asc">Next EMI Due</option>
              <option value="principal_desc">Outstanding Principal</option>
              <option value="emi_desc">EMI Amount</option>
            </select>
            <button type="submit" className="px-3 py-1.5 bg-slate-900 text-white rounded-lg">
              Apply
            </button>
          </form>

          {loading ? (
            <div className="p-8 text-center text-gray-500 text-xs bg-white rounded-xl border border-gray-200">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
              Loading loans...
            </div>
          ) : loans.length === 0 ? (
            <div className="p-10 text-center bg-white rounded-xl border border-gray-200 text-xs">
              <Landmark className="w-10 h-10 text-gray-300 mx-auto mb-2" />
              <div className="font-semibold text-gray-900">No loans registered yet</div>
              <p className="text-gray-500 mt-1">
                Register new or mid-tenure loans to track EMI schedules, principal payoff, and
                interest expenses.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {loans.map((ln) => (
                <div
                  key={ln.id}
                  className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-3 text-xs"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-sm font-bold text-gray-900">{ln.loan_name}</div>
                      <div className="text-gray-500">
                        {ln.lender_name} • {ln.interest_rate}% ({ln.interest_rate_type})
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-slate-100 text-slate-700">
                      {ln.derived_status}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 py-2 border-y border-gray-100">
                    <div>
                      <div className="text-gray-500">Outstanding</div>
                      <div className="font-bold text-rose-700">
                        {formatINR(ln.current_outstanding_principal)}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-500">EMI</div>
                      <div className="font-bold text-gray-900">{formatINR(ln.emi_amount)}</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Next Due</div>
                      <div className="font-semibold text-gray-800">
                        {ln.next_emi_due_date ? formatDate(ln.next_emi_due_date) : 'Settled'}
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] text-gray-500 mb-1">
                      <span>Repayment Progress</span>
                      <span className="font-semibold text-emerald-700">
                        {ln.repayment_progress_pct}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-emerald-600 h-2 rounded-full"
                        style={{ width: `${Math.min(100, Number(ln.repayment_progress_pct))}%` }}
                      />
                    </div>
                  </div>

                  <div className="flex justify-end space-x-2 pt-1">
                    {ln.status !== 'closed' && ln.status !== 'archived' && (
                      <button
                        type="button"
                        onClick={() => {
                          setPayingLoan(ln);
                          setPayingInst(null);
                          setPrepayPreset(null);
                        }}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold"
                      >
                        Record Repayment
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setDetailsLoan(ln)}
                      className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-lg font-medium inline-flex items-center space-x-1"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Schedule &amp; Tools</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'payments' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          {payments.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500">No loan repayments recorded yet.</div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-4">Date</th>
                  <th className="py-2.5 px-3">Loan</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3 text-right">Principal</th>
                  <th className="py-2.5 px-3 text-right">Interest</th>
                  <th className="py-2.5 px-4 text-right">Total Paid</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td className="py-2.5 px-4">{formatDate(p.payment_date)}</td>
                    <td className="py-2.5 px-3 font-semibold">{p.loan_name || '—'}</td>
                    <td className="py-2.5 px-3 uppercase">{p.payment_type}</td>
                    <td className="py-2.5 px-3 text-right text-emerald-700 font-semibold">
                      {formatINR(p.principal_paid)}
                    </td>
                    <td className="py-2.5 px-3 text-right text-amber-700 font-semibold">
                      {formatINR(p.interest_paid)}
                    </td>
                    <td className="py-2.5 px-4 text-right font-bold">{formatINR(p.total_paid)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'calculator' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-5 text-xs">
          <div className="flex items-center space-x-2 font-bold text-gray-900">
            <Calculator className="w-4 h-4 text-blue-600" />
            <span>Deterministic EMI &amp; Amortization Calculator (Python Decimal)</span>
          </div>
          <form onSubmit={handleCalculateEmi} className="grid grid-cols-1 sm:grid-cols-6 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Principal (₹)</label>
              <input
                type="number"
                step="0.01"
                min="1"
                value={calcPrincipal}
                onChange={(e) => setCalcPrincipal(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Rate (% p.a.)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                disabled={calcMethod === 'zero_interest'}
                value={calcMethod === 'zero_interest' ? '0' : calcRate}
                onChange={(e) => setCalcRate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Installments</label>
              <input
                type="number"
                min="1"
                max="600"
                value={calcTenure}
                onChange={(e) => setCalcTenure(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Frequency</label>
              <select
                value={calcFreq}
                onChange={(e) => setCalcFreq(e.target.value as EmiFrequency)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Method</label>
              <select
                value={calcMethod}
                onChange={(e) => setCalcMethod(e.target.value as CalculationMethod)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="reducing_balance">Reducing Balance</option>
                <option value="flat_rate">Flat Rate</option>
                <option value="zero_interest">Zero Interest</option>
              </select>
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={calcLoading}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold"
              >
                Calculate EMI
              </button>
            </div>
          </form>

          {calcResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 bg-slate-50 border border-slate-200 rounded-xl">
                <div>
                  <div className="text-gray-500">Periodic EMI</div>
                  <div className="text-lg font-bold text-blue-700">
                    {formatINR(calcResult.periodic_emi)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Total Interest</div>
                  <div className="text-lg font-bold text-amber-700">
                    {formatINR(calcResult.total_interest)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Total Repayment</div>
                  <div className="text-lg font-bold text-gray-900">
                    {formatINR(calcResult.total_repayment)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Split (P / I)</div>
                  <div className="text-sm font-bold text-gray-800">
                    {calcResult.principal_percentage}% / {calcResult.interest_percentage}%
                  </div>
                </div>
              </div>
              <ul className="list-disc list-inside text-[11px] text-gray-500">
                {calcResult.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {tab === 'analytics' && analytics && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4 text-xs">
          <div className="flex items-center space-x-2 font-bold text-gray-900">
            <TrendingUp className="w-4 h-4 text-emerald-600" />
            <span>
              Loan Liability Analytics (Principal Share {analytics.principal_share_pct}% vs Interest{' '}
              {analytics.interest_share_pct}%)
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
            <div>
              <div className="text-gray-500">Actual Repaid Total</div>
              <div className="font-bold text-gray-900">{formatINR(analytics.total_repayment_actual)}</div>
            </div>
            <div>
              <div className="text-gray-500">Projected Remaining Interest</div>
              <div className="font-bold text-amber-700">
                {formatINR(analytics.projected_remaining_interest)}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Monthly EMI Load</div>
              <div className="font-bold text-indigo-700">
                {formatINR(analytics.monthly_emi_commitment)}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Est. Latest Payoff</div>
              <div className="font-bold text-gray-800">
                {analytics.estimated_latest_maturity_date
                  ? formatDate(analytics.estimated_latest_maturity_date)
                  : '—'}
              </div>
            </div>
          </div>
          {analytics.by_loan.map((item) => (
            <div key={item.loan_id} className="flex justify-between py-2 border-b border-gray-100">
              <span className="font-semibold text-gray-800">
                {item.loan_name} ({item.lender_name})
              </span>
              <span>
                Outstanding: <strong>{formatINR(item.outstanding_principal)}</strong> • Paid P/I:{' '}
                {formatINR(item.principal_repaid)} / {formatINR(item.interest_paid)}
              </span>
            </div>
          ))}
        </div>
      )}

      <LoanFormModal
        isOpen={formOpen}
        editingLoan={editingLoan}
        accounts={accounts}
        onClose={() => setFormOpen(false)}
        onSaved={async (saved) => {
          setFormOpen(false);
          if (detailsLoan?.id === saved.id) setDetailsLoan(saved);
          await loadData();
        }}
      />
      <LoanPaymentModal
        loan={payingLoan}
        installment={payingInst}
        presetPrepayment={prepayPreset}
        accounts={accounts}
        onClose={() => setPayingLoan(null)}
        onRecorded={async (updated) => {
          setPayingLoan(null);
          setDetailsLoan(updated);
          await loadData();
        }}
      />
      <LoanDetailsModal
        loan={detailsLoan}
        accounts={accounts}
        onClose={() => setDetailsLoan(null)}
        onEdit={(l) => {
          setDetailsLoan(null);
          setEditingLoan(l);
          setFormOpen(true);
        }}
        onRecordPayment={(l, inst, preset) => {
          setPayingLoan(l);
          setPayingInst(inst || null);
          setPrepayPreset(preset || null);
        }}
        onUpdated={async (l) => {
          setDetailsLoan(l);
          await loadData();
        }}
      />
    </div>
  );
};
