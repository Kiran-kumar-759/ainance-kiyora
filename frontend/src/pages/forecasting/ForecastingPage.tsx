import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Compass,
  Info,
  PiggyBank,
  RefreshCw,
  ShieldAlert,
  Sliders,
  Trash2,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import { forecastingApi } from '../../services/forecastingApi';
import {
  ConfidenceLabel,
  ForecastEvaluation,
  ForecastingOverview,
  ForecastScenario,
} from '../../types/forecasting';
import { formatDate, formatINR } from '../../lib/formatters';

interface ForecastingPageProps {
  onNavigate: (view: string) => void;
}

type ForecastTab = 'overview' | 'categories' | 'balances' | 'savings' | 'scenarios' | 'accuracy';

const CONFIDENCE_STYLE: Record<ConfidenceLabel, string> = {
  high: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-orange-50 text-orange-700 border-orange-200',
  insufficient_data: 'bg-slate-100 text-slate-600 border-slate-200',
};

const HORIZONS = [
  { days: 7, label: '7 Days' },
  { days: 30, label: '30 Days' },
  { days: 90, label: '90 Days' },
  { days: 180, label: '6 Months' },
  { days: 365, label: '12 Months' },
];

export const ForecastingPage: React.FC<ForecastingPageProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<ForecastTab>('overview');
  const [horizonDays, setHorizonDays] = useState<number>(30);
  const [overview, setOverview] = useState<ForecastingOverview | null>(null);
  const [scenarios, setScenarios] = useState<ForecastScenario[]>([]);
  const [activeScenarioResult, setActiveScenarioResult] = useState<ForecastScenario | null>(null);
  const [evaluations, setEvaluations] = useState<ForecastEvaluation[]>([]);

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [banner, setBanner] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Scenario simulator inputs
  const [scenName, setScenName] = useState('Monthly Expense Control');
  const [incomeDeltaPct, setIncomeDeltaPct] = useState('0');
  const [expenseDeltaPct, setExpenseDeltaPct] = useState('-10');
  const [extraRecurring, setExtraRecurring] = useState('0');
  const [extraLoanPay, setExtraLoanPay] = useState('0');
  const [cancelledSubIds, setCancelledSubIds] = useState<string[]>([]);
  const [selectedCatName, setSelectedCatName] = useState('');
  const [selectedCatAdjPct, setSelectedCatAdjPct] = useState('0');
  const [saveScenario, setSaveScenario] = useState(true);

  const loadOverview = async (days = horizonDays) => {
    setLoading(true);
    try {
      const res = await forecastingApi.getOverview(days);
      setOverview(res);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOverview(horizonDays);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [horizonDays]);

  useEffect(() => {
    if (activeTab === 'scenarios') {
      forecastingApi.listScenarios().then(setScenarios).catch(() => {});
    } else if (activeTab === 'accuracy') {
      forecastingApi.listEvaluations().then(setEvaluations).catch(() => {});
    }
  }, [activeTab]);

  const handleRegenerate = async () => {
    setGenerating(true);
    setBanner(null);
    try {
      const res = await forecastingApi.generateForecast({
        horizon_days: horizonDays,
        force_refresh: true,
      });
      setOverview(res);
      setBanner({ type: 'success', text: `Recalculated ${horizonDays}-day forecast cleanly from PostgreSQL.` });
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    } finally {
      setGenerating(false);
    }
  };

  const handleSimulateScenario = async (e: React.FormEvent) => {
    e.preventDefault();
    setBanner(null);
    try {
      const catAdj: Record<string, number> = {};
      if (selectedCatName && Number(selectedCatAdjPct) !== 0) {
        catAdj[selectedCatName] = Number(selectedCatAdjPct);
      }
      const res = await forecastingApi.runScenario({
        name: scenName.trim() || 'Custom Scenario',
        horizon_days: horizonDays,
        income_delta_pct: Number(incomeDeltaPct || 0),
        expense_delta_pct: Number(expenseDeltaPct || 0),
        extra_recurring_monthly_expense: Number(extraRecurring || 0),
        extra_loan_payment_monthly: Number(extraLoanPay || 0),
        cancelled_subscription_ids: cancelledSubIds,
        category_adjustments_pct: catAdj,
        save_scenario: saveScenario,
      });
      setActiveScenarioResult(res);
      if (saveScenario) {
        const list = await forecastingApi.listScenarios();
        setScenarios(list);
      }
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  const handleResetScenario = () => {
    setScenName('Monthly Expense Control');
    setIncomeDeltaPct('0');
    setExpenseDeltaPct('0');
    setExtraRecurring('0');
    setExtraLoanPay('0');
    setCancelledSubIds([]);
    setSelectedCatName('');
    setSelectedCatAdjPct('0');
    setActiveScenarioResult(null);
  };

  const handleDeleteScenario = async (id: string) => {
    try {
      await forecastingApi.deleteScenario(id);
      setScenarios((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  const handleRunBacktest = async () => {
    setGenerating(true);
    setBanner(null);
    try {
      const ev = await forecastingApi.runAccuracyBacktest(Math.min(Math.max(horizonDays, 14), 90));
      setEvaluations((prev) => [ev, ...prev]);
      setBanner({
        type: 'success',
        text:
          ev.status === 'evaluated'
            ? `Walk-forward backtest evaluated against realized outcomes (cutoff ${ev.cutoff_date}).`
            : ev.notes || 'Insufficient historical window for walk-forward backtest.',
      });
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    } finally {
      setGenerating(false);
    }
  };

  const tabs: { id: ForecastTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'overview', label: 'Overview & Cash Flow', icon: TrendingUp },
    { id: 'categories', label: 'Expenses & Categories', icon: BarChart3 },
    { id: 'balances', label: 'Commitments & Balances', icon: Wallet },
    { id: 'savings', label: 'Savings & Risks', icon: PiggyBank },
    { id: 'scenarios', label: 'Scenario Simulator', icon: Sliders },
    { id: 'accuracy', label: 'Accuracy & Backtesting', icon: Compass },
  ];

  const subCommitments = (overview?.commitments || []).filter(
    (c) => c.source_type === 'subscription' && c.commitment_status === 'confirmed'
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-emerald-600" />
            <span>Financial Forecasting &amp; Predictive Analytics</span>
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Deterministic cash-flow projections, category forecasts, upcoming obligations, balance runway, and scenario modeling.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
            {HORIZONS.map((h) => (
              <button
                key={h.days}
                type="button"
                onClick={() => setHorizonDays(h.days)}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                  horizonDays === h.days
                    ? 'bg-emerald-600 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {h.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            disabled={generating}
            onClick={handleRegenerate}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-60"
          >
            <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
            <span>{generating ? 'Calculating...' : 'Recalculate Forecast'}</span>
          </button>
        </div>
      </div>

      {banner && (
        <div
          className={`px-4 py-3 rounded-lg border text-sm flex items-center justify-between ${
            banner.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          <span>{banner.text}</span>
          <button type="button" onClick={() => setBanner(null)} className="text-xs underline ml-4">
            Dismiss
          </button>
        </div>
      )}

      {/* Sub-navigation */}
      <div className="border-b border-slate-200 overflow-x-auto">
        <nav className="flex space-x-2 min-w-max pb-px">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-2 px-3.5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  active
                    ? 'border-emerald-600 text-emerald-700'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {loading && !overview ? (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-sm text-slate-500">
          Computing predictive cash-flow &amp; balance projections...
        </div>
      ) : null}

      {/* Metadata Status Strip */}
      {overview && (
        <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`px-2 py-0.5 font-semibold rounded border uppercase ${
                CONFIDENCE_STYLE[overview.forecast.confidence_label]
              }`}
            >
              Confidence: {overview.forecast.confidence_label.replace('_', ' ')}
            </span>
            <span className="text-slate-600 font-mono">
              Method: {overview.forecast.method}
            </span>
            <span className="text-slate-500">
              {overview.forecast.observation_count} verified txns • {overview.forecast.historical_days_covered}d history
            </span>
          </div>
          <div className="flex items-center gap-3 text-slate-500">
            {overview.is_stale && (
              <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                New ledger activity detected — click Recalculate Forecast
              </span>
            )}
            <span>As of {formatDate(overview.forecast.as_of_date)} ({overview.forecast.timezone})</span>
          </div>
        </div>
      )}

      {/* Insufficient data banner */}
      {overview && overview.forecast.status === 'insufficient_data' && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 flex items-start gap-3">
          <Info className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-amber-900 space-y-1">
            <div className="font-semibold">Insufficient Historical Data for Full Projection</div>
            <p className="text-xs text-amber-800">
              Record at least 3 non-transfer transactions spanning 14+ days (or import a bank statement / add recurring bills, subscriptions, or loans) to unlock statistical cash-flow, category, and savings projections without fabricated estimates.
            </p>
            <div className="pt-1 flex gap-3">
              <button
                type="button"
                onClick={() => onNavigate('imports')}
                className="text-xs font-semibold underline text-amber-900"
              >
                Import Bank Statement →
              </button>
              <button
                type="button"
                onClick={() => onNavigate('transactions')}
                className="text-xs font-semibold underline text-amber-900"
              >
                Add Transactions →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 1. OVERVIEW & CASH FLOW */}
      {activeTab === 'overview' && overview && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Expected Income ({horizonDays}d)</div>
              <div className="text-2xl font-bold text-emerald-700 mt-1">
                {overview.cashflow.expected_income != null
                  ? formatINR(overview.cashflow.expected_income)
                  : 'Insufficient data'}
              </div>
              <div className="text-xs text-slate-500 mt-1 capitalize">
                Pattern: {overview.income.income_pattern.replace(/_/g, ' ')}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Expected Expenses ({horizonDays}d)</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">
                {overview.cashflow.expected_expense != null
                  ? formatINR(overview.cashflow.expected_expense)
                  : 'Insufficient data'}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {overview.expenses.lower_bound != null && overview.expenses.upper_bound != null
                  ? `Range: ${formatINR(overview.expenses.lower_bound)} – ${formatINR(overview.expenses.upper_bound)}`
                  : `Commitments: ${formatINR(overview.cashflow.known_commitments_total)}`}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Predicted Net Cash Flow</div>
              <div
                className={`text-2xl font-bold mt-1 ${
                  Number(overview.cashflow.predicted_net_cashflow ?? 0) >= 0
                    ? 'text-emerald-700'
                    : 'text-rose-700'
                }`}
              >
                {overview.cashflow.predicted_net_cashflow != null
                  ? formatINR(overview.cashflow.predicted_net_cashflow)
                  : 'Unavailable'}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                Projected closing cash:{' '}
                {overview.cashflow.projected_closing_balance != null
                  ? formatINR(overview.cashflow.projected_closing_balance)
                  : formatINR(overview.cashflow.expected_opening_balance)}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Projected Savings &amp; Alerts</div>
              <div className="text-2xl font-bold text-indigo-700 mt-1">
                {overview.savings.expected_monthly_savings != null
                  ? `${formatINR(overview.savings.expected_monthly_savings)}/mo`
                  : 'Unavailable'}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {overview.risks.length} risk warning(s) •{' '}
                {overview.savings.expected_savings_rate_pct != null
                  ? `${overview.savings.expected_savings_rate_pct}% rate`
                  : 'No savings rate yet'}
              </div>
            </div>
          </div>

          {/* Cash flow visual trajectory */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-slate-900">
                Historical Actuals vs Predicted Cash Flow Trajectory
              </h3>
              <div className="flex items-center gap-3 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-slate-700 inline-block" /> Actual
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-amber-500 inline-block" /> Commitment
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" /> Predicted
                </span>
              </div>
            </div>

            {overview.cashflow.daily_points.length === 0 ? (
              <p className="text-sm text-slate-500">No cash flow data points available yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="py-2 pr-3">Date</th>
                      <th className="py-2 pr-3">Type</th>
                      <th className="py-2 pr-3">Income</th>
                      <th className="py-2 pr-3">Expenses</th>
                      <th className="py-2 pr-3">Commitments</th>
                      <th className="py-2">Projected Balance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {overview.cashflow.daily_points.slice(-14).map((pt, idx) => (
                      <tr key={`${pt.target_date}-${idx}`}>
                        <td className="py-2 pr-3 font-medium text-slate-800">{pt.label}</td>
                        <td className="py-2 pr-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                              pt.source_kind === 'historical_actual'
                                ? 'bg-slate-100 text-slate-700'
                                : pt.source_kind === 'known_commitment'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-emerald-50 text-emerald-700'
                            }`}
                          >
                            {pt.is_prediction ? pt.source_kind.replace('_', ' ') : 'Actual'}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-emerald-700">
                          {pt.income_amount != null ? formatINR(pt.income_amount) : '—'}
                        </td>
                        <td className="py-2 pr-3 text-slate-800">
                          {pt.expense_amount != null ? formatINR(pt.expense_amount) : '—'}
                        </td>
                        <td className="py-2 pr-3 text-amber-700">
                          {pt.commitment_amount != null ? formatINR(pt.commitment_amount) : '—'}
                        </td>
                        <td className="py-2 font-semibold text-slate-900">
                          {pt.projected_closing_balance != null
                            ? formatINR(pt.projected_closing_balance)
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Explanations & Assumptions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
              <h3 className="font-semibold text-slate-900">Why This Forecast Was Generated</h3>
              {overview.explanations.map((ex) => (
                <div key={ex.id} className="p-3 rounded-lg bg-slate-50 border border-slate-100 space-y-1">
                  <div className="text-xs font-semibold text-slate-800">{ex.title}</div>
                  <p className="text-xs text-slate-600">{ex.narrative}</p>
                </div>
              ))}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
              <h3 className="font-semibold text-slate-900">Assumptions &amp; Limitations</h3>
              <ul className="space-y-1.5 text-xs text-slate-600 list-disc pl-4">
                {overview.forecast.assumptions.map((a, idx) => (
                  <li key={`a-${idx}`}>{a}</li>
                ))}
                {overview.forecast.limitations.map((l, idx) => (
                  <li key={`l-${idx}`} className="text-slate-500">
                    {l}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* 2. EXPENSES & CATEGORIES */}
      {activeTab === 'categories' && overview && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Next 7 Days</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {overview.expenses.next_week_estimate != null
                  ? formatINR(overview.expenses.next_week_estimate)
                  : 'Insufficient'}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Next 30 Days</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {overview.expenses.next_month_estimate != null
                  ? formatINR(overview.expenses.next_month_estimate)
                  : 'Insufficient'}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Quarterly (90d)</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {overview.expenses.quarterly_estimate != null
                  ? formatINR(overview.expenses.quarterly_estimate)
                  : 'Insufficient'}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Annualized (12m)</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {overview.expenses.yearly_estimate != null
                  ? formatINR(overview.expenses.yearly_estimate)
                  : 'Need 60d+ data'}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Recent Trend</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {overview.expenses.trend_pct != null ? `${overview.expenses.trend_pct}%` : '—'}
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Hist Monthly Avg</th>
                  <th className="px-4 py-3">Predicted ({horizonDays}d)</th>
                  <th className="px-4 py-3">Expected Range</th>
                  <th className="px-4 py-3">Change %</th>
                  <th className="px-4 py-3">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {overview.categories.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      No categorized expense history available yet.
                    </td>
                  </tr>
                ) : (
                  overview.categories.map((cat) => (
                    <tr key={cat.category_name}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">{cat.category_name}</div>
                        <div className="text-xs text-slate-500">{cat.explanation}</div>
                      </td>
                      <td className="px-4 py-3">{formatINR(cat.historical_monthly_avg)}</td>
                      <td className="px-4 py-3 font-semibold text-slate-900">
                        {cat.predicted_amount != null
                          ? formatINR(cat.predicted_amount)
                          : 'Insufficient data'}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {cat.lower_bound != null && cat.upper_bound != null
                          ? `${formatINR(cat.lower_bound)} – ${formatINR(cat.upper_bound)}`
                          : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {cat.expected_change_pct != null ? `${cat.expected_change_pct}%` : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 text-xs font-medium rounded border capitalize ${
                            CONFIDENCE_STYLE[cat.confidence_label]
                          }`}
                        >
                          {cat.confidence_label.replace('_', ' ')}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3. COMMITMENTS & BALANCES */}
      {activeTab === 'balances' && overview && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {overview.balances.map((acc) => (
              <div key={acc.account_id} className="bg-white rounded-xl border border-slate-200 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-slate-900">{acc.account_name}</h4>
                  <span
                    className={`text-[11px] px-2 py-0.5 rounded uppercase font-medium ${
                      acc.is_liability
                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    }`}
                  >
                    {acc.is_liability ? 'Liability' : acc.account_type}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs bg-slate-50 p-2.5 rounded-lg">
                  <div>
                    <div className="text-slate-500">Current Verified</div>
                    <div className="font-semibold text-slate-900">{formatINR(acc.current_balance)}</div>
                  </div>
                  <div>
                    <div className="text-slate-500">Projected End ({horizonDays}d)</div>
                    <div className="font-semibold text-indigo-700">
                      {acc.projected_end_balance != null
                        ? formatINR(acc.projected_end_balance)
                        : 'Insufficient'}
                    </div>
                  </div>
                </div>
                <p className="text-xs text-slate-500">{acc.assumptions[0]}</p>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                <CalendarClock className="w-4 h-4 text-indigo-600" />
                <span>Upcoming Commitments (Bills, Subscriptions, Loan EMIs &amp; Candidates)</span>
              </h3>
              <span className="text-xs text-slate-500">
                Confirmed Total: <strong>{formatINR(overview.cashflow.known_commitments_total)}</strong>
              </span>
            </div>
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Due Date</th>
                  <th className="px-4 py-3">Obligation</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Amount</th>
                  <th className="px-4 py-3">Status &amp; Certainty</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {overview.commitments.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                      No upcoming commitments scheduled inside the next {horizonDays} days.
                    </td>
                  </tr>
                ) : (
                  overview.commitments.map((c, idx) => (
                    <tr key={`${c.source_id}-${c.due_date}-${idx}`}>
                      <td className="px-4 py-3 font-medium text-slate-800">{formatDate(c.due_date)}</td>
                      <td className="px-4 py-3">{c.name}</td>
                      <td className="px-4 py-3 text-xs capitalize text-slate-600">
                        {c.source_type.replace('_', ' ')} ({c.frequency})
                      </td>
                      <td className="px-4 py-3 font-semibold text-slate-900">
                        {c.expected_amount != null ? (
                          formatINR(c.expected_amount)
                        ) : (
                          <span className="text-amber-700 font-normal">Unknown (Variable)</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <span
                          className={`px-2 py-0.5 rounded border ${
                            c.commitment_status === 'confirmed'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}
                        >
                          {c.amount_certainty.replace(/_/g, ' ')}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. SAVINGS & RISKS */}
      {activeTab === 'savings' && overview && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
            <h3 className="font-semibold text-slate-900">Savings Projection (Informational Estimate)</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="text-xs text-slate-500">Historical Monthly Net</div>
                <div className="text-lg font-bold text-slate-900">
                  {overview.savings.historical_monthly_savings != null
                    ? formatINR(overview.savings.historical_monthly_savings)
                    : '—'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
                <div className="text-xs text-emerald-700">Expected Monthly Savings</div>
                <div className="text-lg font-bold text-emerald-800">
                  {overview.savings.expected_monthly_savings != null
                    ? formatINR(overview.savings.expected_monthly_savings)
                    : 'Insufficient data'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="text-xs text-slate-500">Conservative / Best Case</div>
                <div className="text-sm font-semibold text-slate-800 mt-1">
                  {overview.savings.conservative_monthly_savings != null &&
                  overview.savings.best_case_monthly_savings != null
                    ? `${formatINR(overview.savings.conservative_monthly_savings)} to ${formatINR(overview.savings.best_case_monthly_savings)}`
                    : '—'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="text-xs text-slate-500">Projected Yearly Savings</div>
                <div className="text-lg font-bold text-indigo-700">
                  {overview.savings.projected_yearly_savings != null
                    ? formatINR(overview.savings.projected_yearly_savings)
                    : 'Need higher certainty'}
                </div>
              </div>
            </div>
            <p className="text-xs text-slate-500">{overview.savings.disclaimer}</p>
          </div>

          <div className="space-y-3">
            <h3 className="font-semibold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-600" />
              <span>Cash-Flow &amp; Low-Balance Risk Warnings</span>
            </h3>
            {overview.risks.length === 0 ? (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex items-center gap-3 text-sm text-emerald-800">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <span>No low-balance or commitment-cluster pressure warnings detected for this horizon.</span>
              </div>
            ) : (
              overview.risks.map((risk, idx) => (
                <div key={`${risk.risk_type}-${idx}`} className="bg-white rounded-xl border border-slate-200 p-4 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-semibold text-slate-900 text-sm">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      <span>{risk.title}</span>
                    </div>
                    <span className="px-2 py-0.5 text-xs uppercase font-semibold rounded bg-amber-50 text-amber-700 border border-amber-200">
                      {risk.severity}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600">{risk.description}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 5. SCENARIO SIMULATOR */}
      {activeTab === 'scenarios' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <form onSubmit={handleSimulateScenario} className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">What-If Scenario Simulator (Non-Mutating)</h3>
              <button
                type="button"
                onClick={handleResetScenario}
                className="text-xs text-slate-600 underline"
              >
                Reset
              </button>
            </div>
            <p className="text-xs text-slate-500">
              Hypothetical adjustments never alter actual accounts, bills, subscriptions, loans, or ledger entries.
            </p>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Scenario Name</label>
              <input
                type="text"
                required
                value={scenName}
                onChange={(e) => setScenName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Income Change (%)</label>
                <input
                  type="number"
                  step="1"
                  min="-100"
                  max="500"
                  value={incomeDeltaPct}
                  onChange={(e) => setIncomeDeltaPct(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Expense Change (%)</label>
                <input
                  type="number"
                  step="1"
                  min="-100"
                  max="500"
                  value={expenseDeltaPct}
                  onChange={(e) => setExpenseDeltaPct(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Extra Monthly Expense (₹)</label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={extraRecurring}
                  onChange={(e) => setExtraRecurring(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Extra Loan Payment/mo (₹)</label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={extraLoanPay}
                  onChange={(e) => setExtraLoanPay(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
                />
              </div>
            </div>

            {overview && overview.categories.length > 0 && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Category Adjustment</label>
                  <select
                    value={selectedCatName}
                    onChange={(e) => setSelectedCatName(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white"
                  >
                    <option value="">None</option>
                    {overview.categories.map((c) => (
                      <option key={c.category_name} value={c.category_name}>
                        {c.category_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Category Delta (%)</label>
                  <input
                    type="number"
                    min="-100"
                    max="200"
                    value={selectedCatAdjPct}
                    onChange={(e) => setSelectedCatAdjPct(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
                  />
                </div>
              </div>
            )}

            {subCommitments.length > 0 && (
              <div>
                <div className="text-xs font-medium text-slate-700 mb-1">Hypothetically Cancel Subscriptions</div>
                <div className="space-y-1 max-h-28 overflow-y-auto border border-slate-200 rounded-lg p-2">
                  {subCommitments.map((sub) => (
                    <label key={sub.source_id} className="flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={cancelledSubIds.includes(sub.source_id)}
                        onChange={(e) =>
                          setCancelledSubIds((prev) =>
                            e.target.checked
                              ? [...prev, sub.source_id]
                              : prev.filter((id) => id !== sub.source_id)
                          )
                        }
                      />
                      <span>
                        {sub.name} ({sub.expected_amount != null ? formatINR(sub.expected_amount) : 'Variable'})
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={saveScenario}
                onChange={(e) => setSaveScenario(e.target.checked)}
              />
              <span>Persist scenario comparison to history</span>
            </label>

            <button
              type="submit"
              className="w-full py-2.5 px-4 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
            >
              Simulate Scenario
            </button>
          </form>

          <div className="space-y-4">
            {activeScenarioResult && (
              <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
                <h4 className="font-semibold text-slate-900">
                  Comparison: {activeScenarioResult.name} ({activeScenarioResult.horizon_days}d)
                </h4>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="p-2.5 rounded bg-slate-50">
                    <div className="text-slate-500">Baseline Net</div>
                    <div className="font-bold text-slate-900">
                      {formatINR(activeScenarioResult.baseline_summary.net_cashflow)}
                    </div>
                  </div>
                  <div className="p-2.5 rounded bg-emerald-50">
                    <div className="text-emerald-700">Scenario Net</div>
                    <div className="font-bold text-emerald-800">
                      {formatINR(activeScenarioResult.scenario_summary.net_cashflow)}
                    </div>
                  </div>
                  <div className="p-2.5 rounded bg-indigo-50">
                    <div className="text-indigo-700">Cashflow Delta</div>
                    <div className="font-bold text-indigo-800">
                      {formatINR(activeScenarioResult.delta_summary.cashflow_diff ?? 0)}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-slate-600">
                  Projected Closing Balance: {formatINR(activeScenarioResult.baseline_summary.projected_closing_balance)} →{' '}
                  <strong>{formatINR(activeScenarioResult.scenario_summary.projected_closing_balance)}</strong>
                </div>
              </div>
            )}

            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
              <h4 className="font-semibold text-slate-900">Saved What-If Scenarios</h4>
              {scenarios.length === 0 ? (
                <p className="text-xs text-slate-500">No saved scenarios yet.</p>
              ) : (
                <div className="space-y-2">
                  {scenarios.map((s) => (
                    <div
                      key={s.id || s.name}
                      className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-100 text-xs"
                    >
                      <div>
                        <div className="font-semibold text-slate-900">{s.name} ({s.horizon_days}d)</div>
                        <div className="text-slate-600">
                          Net Delta: {formatINR(s.delta_summary.cashflow_diff ?? 0)} • Closing:{' '}
                          {formatINR(s.scenario_summary.projected_closing_balance)}
                        </div>
                      </div>
                      {s.id && (
                        <button
                          type="button"
                          onClick={() => handleDeleteScenario(s.id!)}
                          aria-label={`Delete ${s.name}`}
                          className="p-1.5 text-slate-400 hover:text-rose-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 6. ACCURACY & BACKTESTING */}
      {activeTab === 'accuracy' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-slate-600">
              Time-aware walk-forward backtesting splits strictly before the cutoff date (zero future data leakage) and evaluates against realized actuals using MAE, RMSE, WAPE, and Bias.
            </div>
            <button
              type="button"
              disabled={generating}
              onClick={handleRunBacktest}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-60"
            >
              Run Walk-Forward Backtest
            </button>
          </div>

          {evaluations.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-sm text-slate-500">
              No backtest evaluations recorded yet. Click &quot;Run Walk-Forward Backtest&quot; to measure historical forecast accuracy.
            </div>
          ) : (
            <div className="space-y-4">
              {evaluations.map((ev) => (
                <div key={ev.id} className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-semibold text-slate-900 text-sm">
                      Cutoff {formatDate(ev.cutoff_date)} → Evaluated {formatDate(ev.eval_start_date)} to{' '}
                      {formatDate(ev.eval_end_date)} ({ev.horizon_days}d)
                    </div>
                    <span className="px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-700 capitalize">
                      {ev.status.replace('_', ' ')}
                    </span>
                  </div>
                  {ev.notes && <p className="text-xs text-slate-600">{ev.notes}</p>}
                  {ev.status === 'evaluated' && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                      <div className="p-2.5 rounded bg-slate-50">
                        <div className="text-slate-500">Predicted vs Actual Expense</div>
                        <div className="font-bold text-slate-900">
                          {formatINR(ev.predicted_expense ?? 0)} / {formatINR(ev.actual_expense ?? 0)}
                        </div>
                      </div>
                      <div className="p-2.5 rounded bg-slate-50">
                        <div className="text-slate-500">MAE (Category)</div>
                        <div className="font-bold text-slate-900">{formatINR(ev.mae_expense ?? 0)}</div>
                      </div>
                      <div className="p-2.5 rounded bg-slate-50">
                        <div className="text-slate-500">WAPE %</div>
                        <div className="font-bold text-slate-900">
                          {ev.wape_expense_pct != null ? `${ev.wape_expense_pct}%` : 'N/A (0 actual)'}
                        </div>
                      </div>
                      <div className="p-2.5 rounded bg-slate-50">
                        <div className="text-slate-500">Bias (Pred - Actual)</div>
                        <div className="font-bold text-slate-900">{formatINR(ev.bias_expense ?? 0)}</div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
