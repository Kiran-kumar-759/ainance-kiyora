import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Bell,
  CalendarClock,
  CreditCard,
  Eye,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { subscriptionsApi } from '../../services/phase6Api';
import { financeApi } from '../../services/financeApi';
import { billsApi } from '../../services/billsApi';
import { FinancialAccount } from '../../types/finance';
import {
  Subscription,
  SubscriptionAnalytics,
  SubscriptionCandidate,
  SubscriptionFrequency,
  SubscriptionOverview,
  SubscriptionPayment,
} from '../../types/phase6';
import { formatDate, formatINR } from '../../lib/formatters';
import {
  SUBSCRIPTION_CATEGORIES,
  SubscriptionDetailsModal,
  SubscriptionFormModal,
  SubscriptionPaymentModal,
} from './SubscriptionModals';

interface SubscriptionsPageProps {
  onNavigate: (view: string) => void;
}

type SubTab = 'active' | 'all' | 'payments' | 'analytics' | 'candidates';

export const SubscriptionsPage: React.FC<SubscriptionsPageProps> = () => {
  const [tab, setTab] = useState<SubTab>('active');
  const [overview, setOverview] = useState<SubscriptionOverview | null>(null);
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [payments, setPayments] = useState<SubscriptionPayment[]>([]);
  const [analytics, setAnalytics] = useState<SubscriptionAnalytics | null>(null);
  const [candidates, setCandidates] = useState<SubscriptionCandidate[]>([]);
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);

  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('next_renewal_asc');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingSub, setEditingSub] = useState<Subscription | null>(null);
  const [draftSub, setDraftSub] = useState<{
    name?: string;
    provider?: string;
    amount?: string;
    frequency?: SubscriptionFrequency;
    nextDate?: string;
  } | null>(null);
  const [payingSub, setPayingSub] = useState<Subscription | null>(null);
  const [detailsSub, setDetailsSub] = useState<Subscription | null>(null);

  useEffect(() => {
    financeApi.listAccounts(false).then(setAccounts).catch(() => {});
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const effectiveStatus = tab === 'active' ? undefined : statusFilter || undefined;
      const [ov, listRes, payRes, anaRes, candRes] = await Promise.all([
        subscriptionsApi.getOverview(),
        subscriptionsApi.listSubscriptions({
          status_filter: effectiveStatus,
          category: catFilter || undefined,
          search: search.trim() || undefined,
          sort_by: sortBy,
          page,
          page_size: 15,
        }),
        subscriptionsApi.listPayments(),
        subscriptionsApi.getAnalytics(),
        subscriptionsApi.listCandidates(),
      ]);
      setOverview(ov);
      const visible =
        tab === 'active'
          ? listRes.items.filter((s) => s.status === 'active' || s.status === 'trial')
          : listRes.items;
      setSubs(visible);
      setTotal(tab === 'active' ? visible.length : listRes.total);
      setTotalPages(listRes.total_pages);
      setPayments(payRes.items);
      setAnalytics(anaRes);
      setCandidates(candRes);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load subscriptions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, page, catFilter, statusFilter, sortBy]);

  const handleRunReminders = async () => {
    try {
      const res = await billsApi.processReminders();
      setBanner(
        `Processed ${res.processed_count} due reminder(s), created ${res.notifications_created} in-app alert(s).`
      );
      await loadData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Reminder check failed.');
    }
  };

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      trial: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      paused: 'bg-amber-50 text-amber-800 border-amber-200',
      cancelled: 'bg-rose-50 text-rose-700 border-rose-200',
      archived: 'bg-gray-100 text-gray-500 border-gray-200',
    };
    return (
      <span
        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
          map[status] || 'bg-gray-100 text-gray-700 border-gray-200'
        }`}
      >
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            OTT &amp; Recurring Subscriptions
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Track streaming, cloud, SaaS, trials, price hikes, and confirmed ledger payments cleanly
            separated from projected renewals.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleRunReminders}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-lg text-xs font-semibold shadow-sm"
          >
            <Bell className="w-4 h-4 text-indigo-600" />
            <span>Run Renewal Reminders</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setEditingSub(null);
              setDraftSub(null);
              setFormOpen(true);
            }}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Add Subscription</span>
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

      {/* Overview Metrics */}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-gray-500">
              Active Subscriptions
            </div>
            <div className="text-2xl font-bold text-emerald-700 mt-1">{overview.active_count}</div>
            <div className="text-xs text-gray-500 mt-0.5">
              {overview.trial_count} trial • {overview.paused_count} paused
            </div>
          </div>

          <div className="bg-white rounded-xl border border-indigo-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-indigo-700">
              Est. Monthly Cost
            </div>
            <div className="text-2xl font-bold text-indigo-700 mt-1">
              {formatINR(overview.monthly_recurring_cost)}
            </div>
            <div className="text-[11px] text-gray-500 mt-0.5">Normalized active schedules</div>
          </div>

          <div className="bg-white rounded-xl border border-blue-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-blue-700">
              Est. Annual Cost
            </div>
            <div className="text-2xl font-bold text-blue-700 mt-1">
              {formatINR(overview.annual_recurring_cost)}
            </div>
            <div className="text-[11px] text-gray-500 mt-0.5">Excludes paused &amp; cancelled</div>
          </div>

          <div className="bg-white rounded-xl border border-amber-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-amber-700">
              Due Soon (&le;{overview.due_soon_threshold_days}d)
            </div>
            <div className="text-2xl font-bold text-amber-700 mt-1">
              {overview.renewals_due_soon_count}
            </div>
            <div className="text-xs text-amber-700 mt-0.5">
              {overview.trials_ending_soon_count} trial(s) ending soon
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-gray-500">
              Actual Spent (Month)
            </div>
            <div className="text-2xl font-bold text-gray-900 mt-1">
              {formatINR(overview.actual_spent_this_month)}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              Total paid: {formatINR(overview.actual_spent_total)}
            </div>
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

      {/* Tabs */}
      <div className="border-b border-gray-200 flex flex-wrap gap-1">
        {[
          { id: 'active', label: 'Active & Trials' },
          { id: 'all', label: 'All Subscriptions' },
          { id: 'payments', label: `Payment History (${payments.length})` },
          { id: 'analytics', label: 'Subscription Analytics' },
          { id: 'candidates', label: `Detected Candidates (${candidates.length})` },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setTab(t.id as SubTab);
              setPage(1);
            }}
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

      {/* Subscriptions Table */}
      {(tab === 'active' || tab === 'all') && (
        <div className="space-y-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              void loadData();
            }}
            className="bg-white p-3.5 rounded-xl border border-gray-200 flex flex-wrap items-center gap-2 text-xs"
          >
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search subscription, provider, plan..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 border border-gray-300 rounded-lg"
              />
            </div>
            <select
              value={catFilter}
              onChange={(e) => setCatFilter(e.target.value)}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Categories</option>
              {SUBSCRIPTION_CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            {tab === 'all' && (
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
              >
                <option value="">All Statuses</option>
                <option value="active">Active</option>
                <option value="trial">Trial</option>
                <option value="paused">Paused</option>
                <option value="cancelled">Cancelled</option>
                <option value="archived">Archived</option>
              </select>
            )}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="next_renewal_asc">Renewal (Earliest)</option>
              <option value="cost_desc">Monthly Cost (High-Low)</option>
              <option value="name_asc">Name (A-Z)</option>
            </select>
            <button type="submit" className="px-3 py-1.5 bg-slate-900 text-white rounded-lg">
              Apply
            </button>
          </form>

          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {loading ? (
              <div className="p-8 text-center text-gray-500 text-xs">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
                Loading subscriptions...
              </div>
            ) : subs.length === 0 ? (
              <div className="p-10 text-center text-xs">
                <CreditCard className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                <div className="font-semibold text-gray-900">No subscriptions tracked yet</div>
                <p className="text-gray-500 mt-1">
                  Add Netflix, Spotify, cloud storage, or review detected candidates from your
                  transactions.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 uppercase text-[10px]">
                    <tr>
                      <th className="py-2.5 px-4">Service / Plan</th>
                      <th className="py-2.5 px-3">Category</th>
                      <th className="py-2.5 px-3">Billing Cycle</th>
                      <th className="py-2.5 px-3 text-right">Price</th>
                      <th className="py-2.5 px-3 text-right">Monthly Eq.</th>
                      <th className="py-2.5 px-3">Next Renewal</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {subs.map((s) => (
                      <tr key={s.id} className="hover:bg-gray-50/70">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-gray-900">{s.subscription_name}</div>
                          <div className="text-[11px] text-gray-500">
                            {[s.provider_name, s.plan_name].filter(Boolean).join(' • ') || '—'}
                          </div>
                        </td>
                        <td className="py-3 px-3 uppercase text-[10px] font-semibold text-gray-600">
                          {s.category.replace('_', ' ')}
                        </td>
                        <td className="py-3 px-3 capitalize">
                          {s.billing_frequency.replace('_', ' ')}
                        </td>
                        <td className="py-3 px-3 text-right font-bold">
                          {s.is_amount_unknown ? (
                            <span className="text-amber-700 italic">Pending</span>
                          ) : (
                            formatINR(s.amount)
                          )}
                        </td>
                        <td className="py-3 px-3 text-right text-indigo-700 font-semibold">
                          {s.monthly_equivalent ? formatINR(s.monthly_equivalent) : '—'}
                        </td>
                        <td className="py-3 px-3">
                          {s.status === 'trial' && s.trial_end_date ? (
                            <span className="text-indigo-700 font-medium">
                              Trial ends {formatDate(s.trial_end_date)}
                            </span>
                          ) : s.next_renewal_date ? (
                            formatDate(s.next_renewal_date)
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="py-3 px-3">{statusBadge(s.status)}</td>
                        <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                          {s.status !== 'cancelled' && s.status !== 'archived' && (
                            <button
                              type="button"
                              onClick={() => setPayingSub(s)}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-semibold"
                            >
                              Record Payment
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setDetailsSub(s)}
                            className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded font-medium inline-flex items-center space-x-1"
                          >
                            <Eye className="w-3 h-3" />
                            <span>Details</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {totalPages > 1 && (
              <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-200 flex justify-between text-xs">
                <span>
                  Total {total} (Page {page} of {totalPages})
                </span>
                <div className="space-x-2">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="px-2.5 py-1 border rounded bg-white disabled:opacity-50"
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="px-2.5 py-1 border rounded bg-white disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Payment History Tab */}
      {tab === 'payments' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          {payments.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500">
              No subscription payments recorded yet.
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-4">Date</th>
                  <th className="py-2.5 px-3">Subscription</th>
                  <th className="py-2.5 px-3">Account</th>
                  <th className="py-2.5 px-3">Method</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-4 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td className="py-2.5 px-4">{formatDate(p.payment_date)}</td>
                    <td className="py-2.5 px-3 font-semibold">{p.subscription_name || '—'}</td>
                    <td className="py-2.5 px-3">{p.account_name || '—'}</td>
                    <td className="py-2.5 px-3 uppercase">{p.payment_method}</td>
                    <td className="py-2.5 px-3 uppercase text-[10px] font-bold">
                      {p.payment_status}
                    </td>
                    <td className="py-2.5 px-4 text-right font-bold text-emerald-700">
                      {formatINR(p.amount_paid)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Analytics Tab */}
      {tab === 'analytics' && analytics && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 text-xs">
          <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
            <div className="font-bold text-gray-900 flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-indigo-600" />
              <span>Projected vs Actual Spend by Category</span>
            </div>
            {analytics.by_category.length === 0 ? (
              <p className="text-gray-400">No subscription analytics data yet.</p>
            ) : (
              analytics.by_category.map((c) => (
                <div key={c.name} className="flex items-center justify-between py-1.5 border-b border-gray-100">
                  <span className="capitalize font-medium text-gray-800">
                    {c.name.replace('_', ' ')} ({c.count})
                  </span>
                  <div className="text-right">
                    <span className="font-bold text-indigo-700">
                      {formatINR(c.monthly_projected)}/mo
                    </span>
                    <span className="text-gray-400 ml-2">Actual: {formatINR(c.actual_spent)}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
            <div className="font-bold text-gray-900 flex items-center space-x-2">
              <CalendarClock className="w-4 h-4 text-emerald-600" />
              <span>Top Subscriptions &amp; Price Changes ({analytics.price_increase_events_count} increases)</span>
            </div>
            {analytics.most_expensive.map((s) => (
              <div key={s.id} className="flex justify-between py-1.5 border-b border-gray-100">
                <span className="font-semibold text-gray-800">{s.subscription_name}</span>
                <span className="font-bold text-gray-900">
                  {formatINR(s.monthly_equivalent)}/mo ({formatINR(s.annual_equivalent)}/yr)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Candidates Tab */}
      {tab === 'candidates' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3 text-xs">
          <div className="flex items-center space-x-2 text-gray-900 font-bold">
            <Sparkles className="w-4 h-4 text-amber-600" />
            <span>Potential Recurring Subscription Candidates (Requires Your Review)</span>
          </div>
          <p className="text-gray-500">
            Detected deterministically from repeated historical expense patterns. Bills, EMIs, and
            utilities are excluded automatically.
          </p>
          {candidates.length === 0 ? (
            <p className="text-gray-400 py-4 text-center">No unreviewed recurring candidates found.</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {candidates.map((c) => (
                <div key={c.merchant_key} className="py-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-bold text-gray-900">{c.display_name}</div>
                    <div className="text-gray-500">{c.confidence_note}</div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingSub(null);
                        setDraftSub({
                          name: c.display_name,
                          provider: c.display_name,
                          amount: String(c.estimated_amount),
                          frequency: c.detected_frequency,
                          nextDate: c.suggested_next_date,
                        });
                        setFormOpen(true);
                      }}
                      className="px-3 py-1.5 bg-blue-600 text-white rounded-lg font-semibold"
                    >
                      Create Subscription
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        await subscriptionsApi.decideCandidate(c.merchant_key, 'ignore');
                        await loadData();
                      }}
                      className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg font-medium"
                    >
                      Ignore
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <SubscriptionFormModal
        isOpen={formOpen}
        editingSub={editingSub}
        accounts={accounts}
        initialDraft={draftSub}
        onClose={() => setFormOpen(false)}
        onSaved={async (saved) => {
          setFormOpen(false);
          if (detailsSub?.id === saved.id) setDetailsSub(saved);
          await loadData();
        }}
      />
      <SubscriptionPaymentModal
        sub={payingSub}
        accounts={accounts}
        onClose={() => setPayingSub(null)}
        onRecorded={async (updated) => {
          setPayingSub(null);
          setDetailsSub(updated);
          await loadData();
        }}
      />
      <SubscriptionDetailsModal
        sub={detailsSub}
        onClose={() => setDetailsSub(null)}
        onEdit={(s) => {
          setDetailsSub(null);
          setEditingSub(s);
          setFormOpen(true);
        }}
        onRecordPayment={(s) => setPayingSub(s)}
        onUpdated={async (s) => {
          setDetailsSub(s);
          await loadData();
        }}
      />
    </div>
  );
};
