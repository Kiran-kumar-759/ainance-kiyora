import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Bell,
  CalendarClock,
  CheckCheck,
  CheckCircle2,
  Clock,
  CreditCard,
  Eye,
  Plus,
  RefreshCw,
  Repeat,
  Search,
  Sparkles,
} from 'lucide-react';
import { billsApi } from '../../services/billsApi';
import { financeApi } from '../../services/financeApi';
import {
  AppNotification,
  Bill,
  BillPayment,
  BillsOverview,
  ProcessRemindersResult,
  RecurrenceSchedule,
} from '../../types/bills';
import { FinancialAccount, FinancialCategory } from '../../types/finance';
import { formatDate, formatINR } from '../../lib/formatters';
import {
  BILL_CATEGORIES,
  BillDetailsModal,
  BillFormModal,
  RecordPaymentModal,
} from './BillModals';

interface BillsPageProps {
  onNavigate: (view: string) => void;
}

type BillsTab =
  | 'all'
  | 'upcoming'
  | 'overdue'
  | 'paid'
  | 'schedules'
  | 'payments'
  | 'notifications';

export const BillsPage: React.FC<BillsPageProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<BillsTab>('all');
  const [overview, setOverview] = useState<BillsOverview | null>(null);
  const [bills, setBills] = useState<Bill[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [schedules, setSchedules] = useState<RecurrenceSchedule[]>([]);
  const [payments, setPayments] = useState<BillPayment[]>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);

  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [categories, setCategories] = useState<FinancialCategory[]>([]);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [sortBy, setSortBy] = useState('due_date_asc');

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reminderBanner, setReminderBanner] = useState<ProcessRemindersResult | null>(null);

  // Modals
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingBill, setEditingBill] = useState<Bill | null>(null);
  const [payingBill, setPayingBill] = useState<Bill | null>(null);
  const [detailsBill, setDetailsBill] = useState<Bill | null>(null);

  useEffect(() => {
    Promise.all([financeApi.listAccounts(false), financeApi.listCategories()])
      .then(([accs, cats]) => {
        setAccounts(accs);
        setCategories(cats);
      })
      .catch(() => {});
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const effectiveStatus =
        activeTab === 'overdue'
          ? 'overdue'
          : activeTab === 'paid'
            ? 'paid'
            : activeTab === 'upcoming'
              ? undefined
              : statusFilter || undefined;

      const [ov, billsRes, schedRes, payRes, notifRes] = await Promise.all([
        billsApi.getOverview(),
        billsApi.listBills({
          status_filter: effectiveStatus,
          bill_category: categoryFilter || undefined,
          bill_type: typeFilter || undefined,
          search: search.trim() || undefined,
          sort_by: activeTab === 'paid' ? 'due_date_desc' : sortBy,
          page,
          page_size: 15,
        }),
        billsApi.listSchedules(),
        billsApi.listPayments(),
        billsApi.listNotifications(false),
      ]);

      setOverview(ov);
      const filteredItems =
        activeTab === 'upcoming'
          ? billsRes.items.filter(
              (b) => b.derived_status === 'upcoming' || b.derived_status === 'due_soon'
            )
          : billsRes.items;
      setBills(filteredItems);
      setTotal(activeTab === 'upcoming' ? filteredItems.length : billsRes.total);
      setTotalPages(billsRes.total_pages);
      setSchedules(schedRes);
      setPayments(payRes.items);
      setNotifications(notifRes.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load bills and reminders.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeTab, page, statusFilter, categoryFilter, typeFilter, sortBy]);

  const handleRunReminders = async () => {
    setError(null);
    try {
      const res = await billsApi.processReminders();
      setReminderBanner(res);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to process due reminders.');
    }
  };

  const handleArchiveBill = async (bill: Bill) => {
    if (!confirm(`Archive "${bill.bill_name}"? Historical payments will remain intact.`)) return;
    try {
      await billsApi.archiveBill(bill.id);
      setDetailsBill(null);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to archive bill.');
    }
  };

  const handleGenerateNext = async (scheduleId: string) => {
    try {
      await billsApi.generateNextOccurrence(scheduleId);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate next occurrence.');
    }
  };

  const handleToggleSchedule = async (sched: RecurrenceSchedule) => {
    try {
      await billsApi.updateSchedule(sched.id, { is_active: !sched.is_active });
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update schedule.');
    }
  };

  const handleMarkNotifRead = async (id: string) => {
    await billsApi.markNotificationRead(id);
    await loadData();
  };

  const handleMarkAllRead = async () => {
    await billsApi.markAllNotificationsRead();
    await loadData();
  };

  const renderStatusBadge = (b: Bill) => {
    const styles: Record<string, string> = {
      upcoming: 'bg-blue-50 text-blue-700 border-blue-200',
      due_soon: 'bg-amber-50 text-amber-800 border-amber-200',
      overdue: 'bg-rose-50 text-rose-700 border-rose-200',
      paid: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      archived: 'bg-gray-100 text-gray-500 border-gray-200',
    };
    const cls = styles[b.derived_status] || 'bg-gray-100 text-gray-700 border-gray-200';
    return (
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${cls}`}>
        {b.derived_status.replace('_', ' ')}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Bills, Payments &amp; Reminders
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Track one-time and recurring Indian bills, schedule reminders, and record payments into
            your double-entry ledger.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
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
            <span>Run Due Reminders</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setEditingBill(null);
              setIsFormOpen(true);
            }}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Add Bill</span>
          </button>
        </div>
      </div>

      {reminderBanner && (
        <div className="p-3.5 bg-indigo-50 border border-indigo-200 rounded-xl text-xs text-indigo-900 flex items-center justify-between gap-2">
          <div>
            Processed <strong>{reminderBanner.processed_count}</strong> due reminder(s) •
            In-App created: <strong>{reminderBanner.notifications_created}</strong> • Email:{' '}
            <strong>{reminderBanner.email_configured ? 'SMTP Configured' : 'Not Configured'}</strong> •
            SMS: <strong>{reminderBanner.sms_configured ? 'Configured' : 'Not Configured'}</strong>
          </div>
          <button
            type="button"
            onClick={() => setReminderBanner(null)}
            className="underline font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Overview Metrics */}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-gray-500">Upcoming</div>
            <div className="text-2xl font-bold text-blue-700 mt-1">{overview.upcoming_count}</div>
            <div className="text-xs text-gray-600 mt-0.5">
              Known: {formatINR(overview.total_upcoming_known_amount)}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-amber-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-amber-700">
              Due Soon (&le;{overview.due_soon_threshold_days}d)
            </div>
            <div className="text-2xl font-bold text-amber-700 mt-1">{overview.due_soon_count}</div>
            <div className="text-[11px] text-gray-500 mt-0.5">Needs upcoming payment</div>
          </div>

          <div className="bg-white rounded-xl border border-rose-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-rose-700">Overdue</div>
            <div className="text-2xl font-bold text-rose-700 mt-1">{overview.overdue_count}</div>
            <div className="text-xs text-rose-600 mt-0.5">
              Known: {formatINR(overview.total_overdue_known_amount)}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-emerald-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-emerald-700">Paid</div>
            <div className="text-2xl font-bold text-emerald-700 mt-1">{overview.paid_count}</div>
            <div className="text-xs text-emerald-700 mt-0.5">
              {formatINR(overview.total_paid_amount)}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="text-[11px] font-semibold uppercase text-gray-500">
              Next Payment Due
            </div>
            {overview.next_payment_due ? (
              <>
                <div className="text-sm font-bold text-gray-900 mt-1 truncate">
                  {overview.next_payment_due.bill_name}
                </div>
                <div className="text-xs text-gray-600 mt-0.5">
                  {formatDate(overview.next_payment_due.due_date)} •{' '}
                  {overview.next_payment_due.is_amount_unknown
                    ? 'Variable'
                    : formatINR(
                        overview.next_payment_due.remaining_due ??
                          overview.next_payment_due.current_amount
                      )}
                </div>
              </>
            ) : (
              <div className="text-xs text-gray-500 mt-2">No unpaid bills pending</div>
            )}
          </div>
        </div>
      )}

      {overview && overview.unknown_variable_bills_count > 0 && (
        <div className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600">
          Note: <strong>{overview.unknown_variable_bills_count}</strong> variable-amount bill(s)
          await actual billed amount entry and are excluded from known ₹ totals rather than shown as
          ₹0.00.
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-center space-x-2">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={loadData} className="underline font-semibold">
            Retry
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 flex flex-wrap gap-1">
        {[
          { id: 'all', label: 'Active Bills' },
          { id: 'upcoming', label: 'Upcoming & Due Soon' },
          { id: 'overdue', label: `Overdue (${overview?.overdue_count ?? 0})` },
          { id: 'paid', label: 'Paid History' },
          { id: 'schedules', label: `Recurring Schedules (${schedules.length})` },
          { id: 'payments', label: `Payments (${payments.length})` },
          {
            id: 'notifications',
            label: `Notifications (${overview?.unread_notifications_count ?? 0})`,
          },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setActiveTab(t.id as BillsTab);
              setPage(1);
            }}
            className={`px-3.5 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === t.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Bills List Views */}
      {(activeTab === 'all' ||
        activeTab === 'upcoming' ||
        activeTab === 'overdue' ||
        activeTab === 'paid') && (
        <div className="space-y-4">
          {/* Search & Filters */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              loadData();
            }}
            className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-wrap items-center gap-2 text-xs"
          >
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search bill name, provider, ref..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 border border-gray-300 rounded-lg"
              />
            </div>

            <select
              aria-label="Filter Category"
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value);
                setPage(1);
              }}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Categories</option>
              {BILL_CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>

            <select
              aria-label="Filter Type"
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">One-Time &amp; Recurring</option>
              <option value="recurring">Recurring Only</option>
              <option value="one_time">One-Time Only</option>
            </select>

            {activeTab === 'all' && (
              <select
                aria-label="Filter Status"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
              >
                <option value="active">Active Unpaid Bills</option>
                <option value="">All Statuses (Incl. Paid)</option>
                <option value="upcoming">Upcoming</option>
                <option value="due_soon">Due Soon</option>
                <option value="overdue">Overdue</option>
                <option value="paid">Paid</option>
                <option value="archived">Archived</option>
              </select>
            )}

            <select
              aria-label="Sort Bills"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="due_date_asc">Due Date (Earliest)</option>
              <option value="due_date_desc">Due Date (Latest)</option>
              <option value="amount_desc">Highest Amount</option>
              <option value="amount_asc">Lowest Amount</option>
              <option value="name_asc">Name (A-Z)</option>
            </select>

            <button
              type="submit"
              className="px-3 py-1.5 bg-slate-900 text-white rounded-lg font-medium"
            >
              Apply
            </button>
          </form>

          {/* Table */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {isLoading ? (
              <div className="p-8 text-center text-gray-500 text-xs">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
                Loading bills...
              </div>
            ) : bills.length === 0 ? (
              <div className="p-10 text-center">
                <CalendarClock className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                <h3 className="text-sm font-semibold text-gray-900">No bills found</h3>
                <p className="text-xs text-gray-500 mt-1">
                  Add electricity, rent, internet, insurance, or credit card bills to track due dates
                  and reminders.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setEditingBill(null);
                    setIsFormOpen(true);
                  }}
                  className="mt-3 px-4 py-2 bg-blue-600 text-white text-xs font-semibold rounded-lg"
                >
                  + Add Your First Bill
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 uppercase text-[10px] font-bold">
                    <tr>
                      <th className="py-2.5 px-4">Bill / Provider</th>
                      <th className="py-2.5 px-3">Category</th>
                      <th className="py-2 px-3">Due Date</th>
                      <th className="py-2 px-3">Schedule</th>
                      <th className="py-2 px-3 text-right">Amount</th>
                      <th className="py-2 px-3">Status</th>
                      <th className="py-2 px-3">Reminders</th>
                      <th className="py-2 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {bills.map((b) => (
                      <tr key={b.id} className="hover:bg-gray-50/70">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-gray-900">{b.bill_name}</div>
                          {b.provider_name && (
                            <div className="text-[11px] text-gray-500">{b.provider_name}</div>
                          )}
                        </td>
                        <td className="py-3 px-3 uppercase text-[10px] font-semibold text-gray-600">
                          {b.bill_category.replace('_', ' ')}
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap font-medium text-gray-800">
                          {formatDate(b.due_date)}
                        </td>
                        <td className="py-3 px-3">
                          {b.bill_type === 'recurring' ? (
                            <span className="inline-flex items-center space-x-1 text-indigo-700 font-medium">
                              <Repeat className="w-3 h-3" />
                              <span className="capitalize">{b.frequency?.replace('_', ' ')}</span>
                            </span>
                          ) : (
                            <span className="text-gray-500">One-Time</span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-right font-bold whitespace-nowrap">
                          {b.is_amount_unknown ? (
                            <span className="text-amber-700 italic font-semibold">
                              Variable (Pending)
                            </span>
                          ) : b.derived_status === 'paid' ? (
                            <div>
                              <span className="text-emerald-700">
                                {formatINR(
                                  b.amount_paid_total && Number(b.amount_paid_total) > 0
                                    ? b.amount_paid_total
                                    : b.current_amount ?? b.expected_amount
                                )}
                              </span>
                              <div className="text-[10px] font-normal text-gray-400">Paid</div>
                            </div>
                          ) : (
                            formatINR(b.remaining_due ?? b.current_amount ?? b.expected_amount)
                          )}
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">{renderStatusBadge(b)}</td>
                        <td className="py-3 px-3 text-[11px] text-gray-500">
                          {b.derived_status === 'paid' ? (
                            <span className="text-gray-400">Stopped (Paid)</span>
                          ) : b.derived_status === 'archived' ? (
                            <span className="text-gray-400">Archived</span>
                          ) : b.reminder_enabled ? (
                            <span className="inline-flex items-center space-x-1 text-emerald-700">
                              <Clock className="w-3 h-3" />
                              <span>
                                {
                                  b.reminders.filter(
                                    (r) => r.is_enabled && r.delivery_status === 'pending'
                                  ).length
                                }{' '}
                                scheduled
                              </span>
                            </span>
                          ) : (
                            'Off'
                          )}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap space-x-1.5">
                          {b.derived_status !== 'paid' && b.derived_status !== 'archived' && (
                            <button
                              type="button"
                              onClick={() => setPayingBill(b)}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-semibold"
                            >
                              Record Payment
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setDetailsBill(b)}
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
              <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-200 flex items-center justify-between text-xs text-gray-600">
                <span>
                  Total {total} bills (Page {page} of {totalPages})
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

      {/* Recurring Schedules Tab */}
      {activeTab === 'schedules' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          {schedules.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500">
              No recurring schedules configured yet.
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-4">Schedule</th>
                  <th className="py-2.5 px-3">Frequency</th>
                  <th className="py-2.5 px-3">Next Due Date</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3">State</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {schedules.map((s) => (
                  <tr key={s.id}>
                    <td className="py-3 px-4 font-semibold text-gray-900">{s.bill_name}</td>
                    <td className="py-3 px-3 capitalize">{s.frequency.replace('_', ' ')}</td>
                    <td className="py-3 px-3">{formatDate(s.next_due_date)}</td>
                    <td className="py-3 px-3 text-right font-bold">
                      {s.is_variable_amount
                        ? 'Variable'
                        : s.expected_amount
                          ? formatINR(s.expected_amount)
                          : '—'}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          s.is_active
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {s.is_active ? 'ACTIVE' : 'PAUSED'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      {s.is_active && (
                        <button
                          type="button"
                          onClick={() => handleGenerateNext(s.id)}
                          className="px-2.5 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded font-medium inline-flex items-center space-x-1"
                        >
                          <Sparkles className="w-3 h-3" />
                          <span>Generate Next</span>
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleToggleSchedule(s)}
                        className="px-2.5 py-1 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded font-medium"
                      >
                        {s.is_active ? 'Pause' : 'Resume'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Payment History Tab */}
      {activeTab === 'payments' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          {payments.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500">
              No bill payments recorded yet.
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-4">Date</th>
                  <th className="py-2.5 px-3">Bill</th>
                  <th className="py-2.5 px-3">Account</th>
                  <th className="py-2.5 px-3">Method</th>
                  <th className="py-2.5 px-3">Reference</th>
                  <th className="py-2.5 px-4 text-right">Amount Paid</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td className="py-2.5 px-4 text-gray-600">{formatDate(p.payment_date)}</td>
                    <td className="py-2.5 px-3 font-semibold text-gray-900">
                      {p.bill_name || 'Bill'}
                    </td>
                    <td className="py-2.5 px-3 text-gray-700">{p.account_name || '—'}</td>
                    <td className="py-2.5 px-3 uppercase font-medium">{p.payment_method}</td>
                    <td className="py-2.5 px-3 font-mono text-gray-500">
                      {p.reference_number || '—'}
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

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-900">
              In-App Bill Notifications ({notifications.length})
            </h2>
            <button
              type="button"
              onClick={handleMarkAllRead}
              className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-xs font-medium inline-flex items-center space-x-1"
            >
              <CheckCheck className="w-3.5 h-3.5" />
              <span>Mark All Read</span>
            </button>
          </div>
          {notifications.length === 0 ? (
            <p className="text-xs text-gray-500 py-6 text-center">No notifications yet.</p>
          ) : (
            <div className="space-y-2">
              {notifications.map((n) => (
                <div
                  key={n.id}
                  className={`p-3 rounded-xl border text-xs flex items-start justify-between gap-3 ${
                    n.is_read ? 'bg-white border-gray-200' : 'bg-blue-50/60 border-blue-200'
                  }`}
                >
                  <div>
                    <div className="font-semibold text-gray-900 flex items-center space-x-2">
                      {!n.is_read && <span className="w-2 h-2 rounded-full bg-blue-600" />}
                      <span>{n.title}</span>
                    </div>
                    <p className="text-gray-600 mt-0.5">{n.message}</p>
                    <div className="text-[10px] text-gray-400 mt-1">{formatDate(n.created_at)}</div>
                  </div>
                  <div className="flex items-center space-x-2 whitespace-nowrap">
                    {n.related_bill_id && (
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            const b = await billsApi.getBill(n.related_bill_id!);
                            setDetailsBill(b);
                          } catch {
                            // ignore
                          }
                        }}
                        className="text-blue-600 hover:underline font-medium inline-flex items-center space-x-1"
                      >
                        <CreditCard className="w-3 h-3" />
                        <span>View Bill</span>
                      </button>
                    )}
                    {!n.is_read && (
                      <button
                        type="button"
                        onClick={() => handleMarkNotifRead(n.id)}
                        className="px-2 py-1 bg-white border border-gray-300 rounded text-[11px] font-medium"
                      >
                        <CheckCircle2 className="w-3 h-3 inline mr-1" />
                        Mark Read
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      <BillFormModal
        isOpen={isFormOpen}
        editingBill={editingBill}
        accounts={accounts}
        categories={categories}
        onClose={() => {
          setIsFormOpen(false);
          setEditingBill(null);
        }}
        onSaved={async (saved) => {
          setIsFormOpen(false);
          setEditingBill(null);
          if (detailsBill && detailsBill.id === saved.id) setDetailsBill(saved);
          await loadData();
        }}
      />

      <RecordPaymentModal
        bill={payingBill}
        accounts={accounts}
        onClose={() => setPayingBill(null)}
        onRecorded={async (updated) => {
          setPayingBill(null);
          if (detailsBill && detailsBill.id === updated.id) setDetailsBill(updated);
          await loadData();
        }}
      />

      <BillDetailsModal
        bill={detailsBill}
        onClose={() => setDetailsBill(null)}
        onEdit={(b) => {
          setDetailsBill(null);
          setEditingBill(b);
          setIsFormOpen(true);
        }}
        onRecordPayment={(b) => {
          setPayingBill(b);
        }}
        onUpdated={async (b) => {
          setDetailsBill(b);
          await loadData();
        }}
        onArchive={handleArchiveBill}
      />
    </div>
  );
};
