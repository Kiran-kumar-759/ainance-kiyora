import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Bell,
  BellRing,
  CalendarClock,
  CheckCheck,
  CheckCircle2,
  Clock,
  Info,
  Mail,
  RefreshCw,
  Send,
  ShieldAlert,
  Sliders,
  XCircle,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../components/ui/ToastProvider';
import {
  Button,
  EmptyState,
  ErrorBanner,
  MetricCard,
  PageHeader,
  SkeletonCard,
} from '../../components/ui/Primitives';
import { Badge } from '../../components/common/Badge';
import { billsApi } from '../../services/billsApi';
import { loansApi, subscriptionsApi } from '../../services/phase6Api';
import { emailIngestionApi } from '../../services/documentsApi';
import { integrationsApi } from '../../services/integrationsApi';
import { authApi } from '../../services/authApi';
import { AppNotification, Bill, BillReminder, ProcessRemindersResult } from '../../types/bills';
import { Loan, Subscription } from '../../types/phase6';
import { EmailConnection } from '../../types/documents';
import { IntegrationItem, IntegrationTestResult } from '../../types/integrations';
import { formatDate, formatINR } from '../../lib/formatters';

interface RemindersPageProps {
  onNavigate: (view: string) => void;
}

type LogFilter = 'all' | 'scheduled' | 'delivered' | 'failed' | 'unavailable';

interface UnifiedReminderRow {
  id: string;
  sourceType: 'bill' | 'subscription' | 'loan';
  sourceId: string;
  sourceName: string;
  dueDate?: string | null;
  amount?: string | number | null;
  reminderAt: string;
  offsetDays: number;
  channels: string[];
  deliveryStatus: string;
  isEnabled: boolean;
  retryCount: number;
  maxRetries: number;
  channelOutcomes: Record<string, { status: string; detail: string; provider?: string }>;
}

export const RemindersPage: React.FC<RemindersPageProps> = ({ onNavigate }) => {
  const { user, preferences, refreshUser } = useAuth();
  const { pushToast } = useToast();

  const [bills, setBills] = useState<Bill[]>([]);
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [smtpProvider, setSmtpProvider] = useState<IntegrationItem | null>(null);
  const [smtpTestResult, setSmtpTestResult] = useState<IntegrationTestResult | null>(null);
  const [emailConnections, setEmailConnections] = useState<EmailConnection[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [processResult, setProcessResult] = useState<ProcessRemindersResult | null>(null);
  const [testingSmtp, setTestingSmtp] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const [logFilter, setLogFilter] = useState<LogFilter>('all');
  const [activeSection, setActiveSection] = useState<'overview' | 'schedules' | 'inbox'>('overview');

  // Global notification toggle states synced from preferences
  const [billAlertsEnabled, setBillAlertsEnabled] = useState<boolean>(true);
  const [emiAlertsEnabled, setEmiAlertsEnabled] = useState<boolean>(true);
  const [savingGlobalPrefs, setSavingGlobalPrefs] = useState(false);

  // Honest Custom Email Composer state (no backend endpoint for arbitrary ad-hoc sends yet)
  const [customSubject, setCustomSubject] = useState('Upcoming Payment Reminder');
  const [customBody, setCustomBody] = useState('');

  useEffect(() => {
    const np = preferences?.notification_preferences || {};
    setBillAlertsEnabled(np.bill_reminders !== false);
    setEmiAlertsEnabled(np.emi_reminders !== false);
  }, [preferences]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [billsRes, subsRes, loansRes, notifRes, smtpRes, gmailRes] = await Promise.allSettled([
        billsApi.listBills({ status_filter: 'active', page_size: 100 }),
        subscriptionsApi.listSubscriptions({ page_size: 100 }),
        loansApi.listLoans({ page_size: 100 }),
        billsApi.listNotifications(false),
        integrationsApi.getProvider('smtp'),
        emailIngestionApi.getConnections(),
      ]);

      if (billsRes.status === 'fulfilled') setBills(billsRes.value.items || []);
      if (subsRes.status === 'fulfilled') setSubs(subsRes.value.items || []);
      if (loansRes.status === 'fulfilled') setLoans(loansRes.value.items || []);
      if (notifRes.status === 'fulfilled') {
        setNotifications(notifRes.value.items || []);
        setUnreadCount(notifRes.value.unread_count ?? 0);
      }
      if (smtpRes.status === 'fulfilled') setSmtpProvider(smtpRes.value);
      if (gmailRes.status === 'fulfilled') setEmailConnections(gmailRes.value || []);

      if (
        billsRes.status === 'rejected' &&
        subsRes.status === 'rejected' &&
        loansRes.status === 'rejected'
      ) {
        setError('Unable to load bills, subscriptions, or loan reminder schedules.');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load reminders workspace.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const unifiedReminders = useMemo<UnifiedReminderRow[]>(() => {
    const rows: UnifiedReminderRow[] = [];
    const pushRows = (
      reminders: BillReminder[] | undefined,
      meta: {
        sourceType: 'bill' | 'subscription' | 'loan';
        sourceId: string;
        sourceName: string;
        dueDate?: string | null;
        amount?: string | number | null;
      }
    ) => {
      (reminders || []).forEach((r) => {
        rows.push({
          id: r.id,
          sourceType: meta.sourceType,
          sourceId: meta.sourceId,
          sourceName: meta.sourceName,
          dueDate: meta.dueDate,
          amount: meta.amount,
          reminderAt: r.reminder_at,
          offsetDays: r.offset_days,
          channels: r.channels || [],
          deliveryStatus: r.delivery_status,
          isEnabled: r.is_enabled,
          retryCount: r.retry_count,
          maxRetries: r.max_retries,
          channelOutcomes: r.channel_outcomes || {},
        });
      });
    };

    bills.forEach((b) =>
      pushRows(b.reminders, {
        sourceType: 'bill',
        sourceId: b.id,
        sourceName: b.bill_name,
        dueDate: b.due_date,
        amount: b.expected_amount,
      })
    );
    subs.forEach((s) =>
      pushRows(s.reminders, {
        sourceType: 'subscription',
        sourceId: s.id,
        sourceName: s.subscription_name,
        dueDate: s.next_renewal_date,
        amount: s.amount,
      })
    );
    loans.forEach((l) =>
      pushRows(l.reminders, {
        sourceType: 'loan',
        sourceId: l.id,
        sourceName: l.loan_name,
        dueDate: l.next_emi_due_date,
        amount: l.emi_amount,
      })
    );

    return rows.sort((a, b) => a.reminderAt.localeCompare(b.reminderAt));
  }, [bills, subs, loans]);

  const stats = useMemo(() => {
    let scheduled = 0;
    let delivered = 0;
    let failed = 0;
    let unavailable = 0;
    unifiedReminders.forEach((r) => {
      const s = (r.deliveryStatus || '').toLowerCase();
      if (s === 'sent' || s === 'delivered' || s === 'completed') delivered += 1;
      else if (s === 'failed') failed += 1;
      else if (s === 'unavailable' || s === 'skipped') unavailable += 1;
      else scheduled += 1;
    });
    return { scheduled, delivered, failed, unavailable, total: unifiedReminders.length };
  }, [unifiedReminders]);

  const filteredReminders = useMemo(() => {
    if (logFilter === 'all') return unifiedReminders;
    return unifiedReminders.filter((r) => {
      const s = (r.deliveryStatus || '').toLowerCase();
      if (logFilter === 'delivered') return s === 'sent' || s === 'delivered' || s === 'completed';
      if (logFilter === 'failed') return s === 'failed';
      if (logFilter === 'unavailable') return s === 'unavailable' || s === 'skipped';
      return s !== 'sent' && s !== 'delivered' && s !== 'completed' && s !== 'failed' && s !== 'unavailable' && s !== 'skipped';
    });
  }, [unifiedReminders, logFilter]);

  const handleDispatchDueReminders = async () => {
    setProcessing(true);
    setProcessResult(null);
    try {
      const res = await billsApi.processReminders();
      setProcessResult(res);
      pushToast({
        tone: 'success',
        title: 'Due reminders processed',
        description: `Processed ${res.processed_count} reminder(s): ${res.delivered_count} delivered, ${res.failed_count} failed.`,
      });
      await loadAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to dispatch reminders.';
      pushToast({ tone: 'error', title: 'Dispatch failed', description: msg });
    } finally {
      setProcessing(false);
    }
  };

  const handleTestSmtp = async () => {
    setTestingSmtp(true);
    setSmtpTestResult(null);
    try {
      const res = await integrationsApi.testProvider('smtp');
      setSmtpTestResult(res);
      pushToast({
        tone: res.success ? 'success' : 'warning',
        title: res.success ? 'SMTP handshake succeeded' : 'SMTP check reported issue',
        description: res.message,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'SMTP connectivity check failed.';
      pushToast({ tone: 'error', title: 'SMTP Test Failed', description: msg });
    } finally {
      setTestingSmtp(false);
    }
  };

  const handleSaveGlobalToggles = async (nextBills: boolean, nextEmi: boolean) => {
    setSavingGlobalPrefs(true);
    try {
      await authApi.updatePreferences({
        notification_preferences: {
          ...(preferences?.notification_preferences || {}),
          bill_reminders: nextBills,
          emi_reminders: nextEmi,
        },
      });
      setBillAlertsEnabled(nextBills);
      setEmiAlertsEnabled(nextEmi);
      await refreshUser();
      pushToast({ tone: 'success', title: 'Reminder preferences saved' });
    } catch (err: unknown) {
      pushToast({
        tone: 'error',
        title: 'Failed to update preferences',
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setSavingGlobalPrefs(false);
    }
  };

  const handleToggleCommitmentReminder = async (
    type: 'bill' | 'subscription' | 'loan',
    id: string,
    nextEnabled: boolean
  ) => {
    setUpdatingId(id);
    try {
      if (type === 'bill') {
        await billsApi.updateReminders(id, { reminder_enabled: nextEnabled });
      } else if (type === 'subscription') {
        await subscriptionsApi.updateSubscription(id, { reminder_enabled: nextEnabled });
      } else {
        await loansApi.updateLoan(id, { reminder_enabled: nextEnabled });
      }
      pushToast({
        tone: 'success',
        title: `Reminders ${nextEnabled ? 'enabled' : 'paused'}`,
      });
      await loadAll();
    } catch (err: unknown) {
      pushToast({
        tone: 'error',
        title: 'Unable to update reminder toggle',
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setUpdatingId(null);
    }
  };

  const handleMarkRead = async (id: string) => {
    try {
      await billsApi.markNotificationRead(id);
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // ignore
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await billsApi.markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  };

  const statusBadge = (status: string) => {
    const norm = (status || '').toLowerCase();
    if (norm === 'sent' || norm === 'delivered' || norm === 'completed') {
      return <Badge variant="success">Delivered</Badge>;
    }
    if (norm === 'failed') {
      return <Badge variant="danger">Failed</Badge>;
    }
    if (norm === 'unavailable' || norm === 'skipped') {
      return <Badge variant="warning">{status}</Badge>;
    }
    return <Badge variant="info">Scheduled</Badge>;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reminders & Notifications"
        subtitle="Manage bill, subscription, and EMI reminder schedules, trigger due dispatches, and monitor SMTP vs Gmail integration channels."
        badge={<Badge variant="info">{unreadCount} Unread Alerts</Badge>}
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void loadAll()}
              loading={loading}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
            <Button
              variant="indigo"
              size="sm"
              onClick={handleDispatchDueReminders}
              loading={processing}
              icon={<Send className="w-3.5 h-3.5" />}
            >
              Evaluate &amp; Dispatch Due Reminders
            </Button>
          </>
        }
      />

      {error && <ErrorBanner message={error} onRetry={loadAll} />}

      {processResult && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50/90 px-4 py-3 text-xs text-indigo-950 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-indigo-600 shrink-0" />
            <span>
              Reminder batch executed: <strong>{processResult.processed_count}</strong> processed •{' '}
              <strong>{processResult.delivered_count}</strong> delivered •{' '}
              <strong>{processResult.unavailable_count}</strong> unavailable •{' '}
              <strong>{processResult.failed_count}</strong> failed.
            </span>
          </div>
          <span className="text-[11px] text-indigo-700 font-medium">
            Reminders do not automatically mark commitments as paid.
          </span>
        </div>
      )}

      {/* Safety Disclaimer */}
      <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-600 flex items-start gap-2.5 shadow-card">
        <Info className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
        <span>
          <strong>Financial Ledger Safeguard:</strong> Sending or delivering a reminder never marks
          a bill, OTT subscription, or loan EMI as paid. Record payments explicitly after verifying
          your transaction.
        </span>
      </div>

      {/* Summary Metrics */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonCard key={i} rows={1} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <MetricCard
            label="Scheduled Upcoming"
            value={stats.scheduled}
            tone="indigo"
            icon={<Clock className="w-4 h-4" />}
          />
          <MetricCard
            label="Delivered"
            value={stats.delivered}
            tone="emerald"
            icon={<CheckCircle2 className="w-4 h-4" />}
          />
          <MetricCard
            label="Failed"
            value={stats.failed}
            tone="rose"
            icon={<XCircle className="w-4 h-4" />}
          />
          <MetricCard
            label="Skipped / Unavailable"
            value={stats.unavailable}
            tone="amber"
            icon={<ShieldAlert className="w-4 h-4" />}
          />
          <MetricCard
            label="Outbound SMTP"
            value={smtpProvider?.configured ? 'Configured' : 'Not Configured'}
            helper={
              smtpProvider?.configured
                ? 'Ready for email delivery'
                : 'Configure SMTP_* env vars'
            }
            icon={<Mail className="w-4 h-4" />}
          />
        </div>
      )}

      {/* Sub-navigation Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {[
          { id: 'overview', label: 'Channels & Controls', icon: Sliders },
          {
            id: 'schedules',
            label: `Reminder Schedule & Logs (${unifiedReminders.length})`,
            icon: CalendarClock,
          },
          { id: 'inbox', label: `In-App Inbox (${unreadCount} unread)`, icon: Bell },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeSection === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveSection(tab.id as typeof activeSection)}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors ${
                active
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* SECTION 1: Channels, Inbound vs Outbound Separation & Commitment Toggles */}
      {activeSection === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Inbound vs Outbound Separation Card */}
            <div className="rounded-2xl bg-white border border-slate-200/80 p-5 shadow-card space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Outbound SMTP vs Inbound Gmail Channel Status
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Gmail OAuth is strictly read-only ingestion; outbound reminder emails require
                    server SMTP.
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => onNavigate('integrations')}
                >
                  Open Integrations
                </Button>
              </div>

              {/* Outbound SMTP Box */}
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Mail className="w-4 h-4 text-indigo-600" />
                    <span className="text-xs font-bold text-slate-900">
                      Outbound Email Channel (SMTP)
                    </span>
                  </div>
                  <Badge variant={smtpProvider?.configured ? 'success' : 'warning'}>
                    {smtpProvider?.configured ? 'Configured' : 'Not Configured'}
                  </Badge>
                </div>
                <p className="text-xs text-slate-600">
                  {smtpProvider?.last_error
                    ? smtpProvider.last_error
                    : smtpProvider?.description ||
                      'SMTP relays reminder alerts to your verified user email address.'}
                </p>
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <Button
                    variant="outline"
                    size="xs"
                    loading={testingSmtp}
                    onClick={handleTestSmtp}
                  >
                    Test SMTP Connectivity (NOOP)
                  </Button>
                  {smtpTestResult && (
                    <span
                      className={`text-[11px] font-medium ${
                        smtpTestResult.success ? 'text-emerald-700' : 'text-rose-700'
                      }`}
                    >
                      {smtpTestResult.message}
                    </span>
                  )}
                </div>
              </div>

              {/* Inbound Gmail Box */}
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-slate-900">
                    Inbound Bill Ingestion (Gmail OAuth — Read-Only)
                  </span>
                  <Badge
                    variant={
                      emailConnections.some((c) => c.status === 'active') ? 'info' : 'neutral'
                    }
                  >
                    {emailConnections.some((c) => c.status === 'active')
                      ? `${emailConnections.filter((c) => c.status === 'active').length} Connected`
                      : 'Not Connected'}
                  </Badge>
                </div>
                <p className="text-xs text-slate-600">
                  {emailConnections.length > 0
                    ? `Connected: ${emailConnections.map((c) => c.email_address).join(', ')} (used strictly to fetch & parse vendor bills)`
                    : 'No Gmail inbox connected for automatic bill extraction.'}
                </p>
                <button
                  type="button"
                  onClick={() => onNavigate('documents')}
                  className="text-xs font-semibold text-indigo-600 hover:underline"
                >
                  Manage Email Bill Imports in Documents &rarr;
                </button>
              </div>
            </div>

            {/* Global Toggle + Honest Custom Email Composer Card */}
            <div className="space-y-5">
              <div className="rounded-2xl bg-white border border-slate-200/80 p-5 shadow-card space-y-3">
                <h3 className="text-sm font-bold text-slate-900">Global Automated Alert Toggles</h3>
                <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer">
                  <div>
                    <p className="text-xs font-semibold text-slate-900">
                      Bill &amp; Subscription Reminders
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Enable automated reminders ahead of utility and OTT renewal due dates
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={billAlertsEnabled}
                    disabled={savingGlobalPrefs}
                    onChange={(e) => void handleSaveGlobalToggles(e.target.checked, emiAlertsEnabled)}
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer">
                  <div>
                    <p className="text-xs font-semibold text-slate-900">Loan &amp; EMI Reminders</p>
                    <p className="text-[11px] text-slate-500">
                      Receive upcoming installment alerts prior to monthly EMI debit dates
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={emiAlertsEnabled}
                    disabled={savingGlobalPrefs}
                    onChange={(e) => void handleSaveGlobalToggles(billAlertsEnabled, e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </label>
              </div>

              {/* Honest Backend Gap Notice for Ad-hoc Custom Email Dispatch */}
              <div className="rounded-2xl bg-white border border-amber-200/90 p-5 shadow-card space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-bold text-slate-900">
                    Ad-Hoc Custom Reminder Email Composer
                  </h3>
                  <Badge variant="warning">Backend Endpoint Unavailable</Badge>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Recipient target: <strong>{user?.email || 'Registered user email'}</strong>.
                  Custom-subject manual email sending and template saving are{' '}
                  <strong>not yet exposed by a backend endpoint</strong> (only schedule-based due
                  dispatch via <code className="text-[11px]">POST /api/v1/bills/reminders/process</code>{' '}
                  is available).
                </p>
                <div className="space-y-2 opacity-75">
                  <input
                    type="text"
                    value={customSubject}
                    onChange={(e) => setCustomSubject(e.target.value)}
                    disabled
                    aria-label="Custom reminder subject (disabled until backend support)"
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-slate-50 text-slate-500"
                  />
                  <textarea
                    rows={2}
                    value={customBody}
                    onChange={(e) => setCustomBody(e.target.value)}
                    disabled
                    placeholder="Custom reminder email notes require POST /api/v1/notifications/send-custom on backend."
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-slate-50 text-slate-500"
                  />
                </div>
                <Button variant="outline" size="xs" disabled>
                  Send Custom Email (Requires Backend API)
                </Button>
              </div>
            </div>
          </div>

          {/* Per-Commitment Reminder Controls */}
          <div className="rounded-2xl bg-white border border-slate-200/80 p-5 shadow-card space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Per-Commitment Reminder Schedules
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Toggle reminders on or off across your active Bills, OTT Subscriptions, and Loans.
                </p>
              </div>
            </div>

            {bills.length === 0 && subs.length === 0 && loans.length === 0 ? (
              <EmptyState
                icon={<BellRing className="w-5 h-5" />}
                title="No commitments found"
                description="Add a bill, subscription, or loan to configure automated payment reminders."
                action={
                  <Button variant="primary" size="xs" onClick={() => onNavigate('bills')}>
                    Go to Bills
                  </Button>
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500 font-semibold">
                      <th className="py-2.5 pr-4">Commitment</th>
                      <th className="py-2.5 pr-4">Type</th>
                      <th className="py-2.5 pr-4">Next Due / Renewal</th>
                      <th className="py-2.5 pr-4">Lead Days</th>
                      <th className="py-2.5 pr-4">Channels</th>
                      <th className="py-2.5 text-right">Auto-Remind</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {bills.map((b) => (
                      <tr key={`bill-${b.id}`} className="hover:bg-slate-50/70">
                        <td className="py-2.5 pr-4 font-semibold text-slate-900">
                          {b.bill_name}
                          {b.expected_amount && (
                            <span className="ml-2 text-slate-500 font-normal tabular-nums">
                              ({formatINR(b.expected_amount)})
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 pr-4">
                          <Badge variant="info">Bill</Badge>
                        </td>
                        <td className="py-2.5 pr-4 text-slate-600">{formatDate(b.due_date)}</td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {(b.reminder_days_before || []).join(', ') || 'None'} d
                        </td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {Object.entries(b.notification_channels || {})
                            .filter(([, v]) => v)
                            .map(([k]) => k)
                            .join(', ') || 'in_app'}
                        </td>
                        <td className="py-2.5 text-right">
                          <Button
                            variant={b.reminder_enabled ? 'primary' : 'outline'}
                            size="xs"
                            loading={updatingId === b.id}
                            onClick={() =>
                              void handleToggleCommitmentReminder('bill', b.id, !b.reminder_enabled)
                            }
                          >
                            {b.reminder_enabled ? 'Enabled' : 'Paused'}
                          </Button>
                        </td>
                      </tr>
                    ))}
                    {subs.map((s) => (
                      <tr key={`sub-${s.id}`} className="hover:bg-slate-50/70">
                        <td className="py-2.5 pr-4 font-semibold text-slate-900">
                          {s.subscription_name}
                          {s.amount && (
                            <span className="ml-2 text-slate-500 font-normal tabular-nums">
                              ({formatINR(s.amount)})
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 pr-4">
                          <Badge variant="violet">Subscription</Badge>
                        </td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {s.next_renewal_date ? formatDate(s.next_renewal_date) : '—'}
                        </td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {(s.reminder_days_before || []).join(', ') || 'None'} d
                        </td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {Object.entries(s.notification_channels || {})
                            .filter(([, v]) => v)
                            .map(([k]) => k)
                            .join(', ') || 'in_app'}
                        </td>
                        <td className="py-2.5 text-right">
                          <Button
                            variant={s.reminder_enabled ? 'primary' : 'outline'}
                            size="xs"
                            loading={updatingId === s.id}
                            onClick={() =>
                              void handleToggleCommitmentReminder(
                                'subscription',
                                s.id,
                                !s.reminder_enabled
                              )
                            }
                          >
                            {s.reminder_enabled ? 'Enabled' : 'Paused'}
                          </Button>
                        </td>
                      </tr>
                    ))}
                    {loans.map((l) => (
                      <tr key={`loan-${l.id}`} className="hover:bg-slate-50/70">
                        <td className="py-2.5 pr-4 font-semibold text-slate-900">
                          {l.loan_name}
                          <span className="ml-2 text-slate-500 font-normal tabular-nums">
                            ({formatINR(l.emi_amount)}/mo)
                          </span>
                        </td>
                        <td className="py-2.5 pr-4">
                          <Badge variant="neutral">Loan EMI</Badge>
                        </td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {l.next_emi_due_date ? formatDate(l.next_emi_due_date) : '—'}
                        </td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {(l.reminder_days_before || []).join(', ') || 'None'} d
                        </td>
                        <td className="py-2.5 pr-4 text-slate-600">
                          {Object.entries(l.notification_channels || {})
                            .filter(([, v]) => v)
                            .map(([k]) => k)
                            .join(', ') || 'in_app'}
                        </td>
                        <td className="py-2.5 text-right">
                          <Button
                            variant={l.reminder_enabled ? 'primary' : 'outline'}
                            size="xs"
                            loading={updatingId === l.id}
                            onClick={() =>
                              void handleToggleCommitmentReminder('loan', l.id, !l.reminder_enabled)
                            }
                          >
                            {l.reminder_enabled ? 'Enabled' : 'Paused'}
                          </Button>
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

      {/* SECTION 2: Filterable Schedule & Delivery History Log */}
      {activeSection === 'schedules' && (
        <div className="rounded-2xl bg-white border border-slate-200/80 p-5 shadow-card space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-slate-900">
              Scheduled &amp; Dispatched Reminder Audit Log
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {(['all', 'scheduled', 'delivered', 'failed', 'unavailable'] as LogFilter[]).map(
                (f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setLogFilter(f)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium capitalize ${
                      logFilter === f
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {f}
                  </button>
                )
              )}
            </div>
          </div>

          {filteredReminders.length === 0 ? (
            <EmptyState
              icon={<CalendarClock className="w-5 h-5" />}
              title="No reminder entries match this filter"
              description="Try switching filter tabs or click Evaluate & Dispatch Due Reminders to process upcoming commitments."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 font-semibold">
                    <th className="py-2.5 pr-4">Commitment</th>
                    <th className="py-2.5 pr-4">Reminder Trigger Time</th>
                    <th className="py-2.5 pr-4">Offset</th>
                    <th className="py-2.5 pr-4">Channels</th>
                    <th className="py-2.5 pr-4">Status</th>
                    <th className="py-2.5 pr-4">Retries / Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredReminders.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-50/70">
                      <td className="py-2.5 pr-4">
                        <p className="font-semibold text-slate-900">{row.sourceName}</p>
                        <p className="text-[11px] text-slate-500 capitalize">
                          {row.sourceType}
                          {row.dueDate ? ` • Due ${formatDate(row.dueDate)}` : ''}
                        </p>
                      </td>
                      <td className="py-2.5 pr-4 text-slate-700 whitespace-nowrap">
                        {formatDate(row.reminderAt)}
                      </td>
                      <td className="py-2.5 pr-4 text-slate-600">
                        {row.offsetDays === 0 ? 'On due date' : `${row.offsetDays}d before`}
                      </td>
                      <td className="py-2.5 pr-4 text-slate-600">
                        {row.channels.join(', ') || 'in_app'}
                      </td>
                      <td className="py-2.5 pr-4">{statusBadge(row.deliveryStatus)}</td>
                      <td className="py-2.5 pr-4 text-[11px] text-slate-500">
                        {row.retryCount}/{row.maxRetries} retries
                        {Object.entries(row.channelOutcomes).length > 0 && (
                          <div className="mt-0.5 text-slate-600">
                            {Object.entries(row.channelOutcomes)
                              .map(([ch, out]) => `${ch}: ${out.status}${out.detail ? ` (${out.detail})` : ''}`)
                              .join(' • ')}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* SECTION 3: In-App Notification Inbox */}
      {activeSection === 'inbox' && (
        <div className="rounded-2xl bg-white border border-slate-200/80 p-5 shadow-card space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900">In-App Notification History</h3>
            {unreadCount > 0 && (
              <Button
                variant="outline"
                size="xs"
                onClick={handleMarkAllRead}
                icon={<CheckCheck className="w-3.5 h-3.5" />}
              >
                Mark All Read
              </Button>
            )}
          </div>

          {notifications.length === 0 ? (
            <EmptyState
              icon={<Bell className="w-5 h-5" />}
              title="Inbox is empty"
              description="Delivered bill, subscription renewal, and EMI reminders will appear here."
            />
          ) : (
            <div className="divide-y divide-slate-100">
              {notifications.map((n) => (
                <div
                  key={n.id}
                  className={`py-3.5 px-3 rounded-xl flex items-start justify-between gap-3 ${
                    n.is_read ? '' : 'bg-indigo-50/45'
                  }`}
                >
                  <div className="flex items-start gap-2.5 min-w-0">
                    <AlertCircle
                      className={`w-4 h-4 shrink-0 mt-0.5 ${
                        n.is_read ? 'text-slate-400' : 'text-indigo-600'
                      }`}
                    />
                    <div>
                      <p className="text-xs font-semibold text-slate-900">{n.title}</p>
                      <p className="text-xs text-slate-600 mt-0.5">{n.message}</p>
                      <p className="text-[11px] text-slate-400 mt-1">
                        {formatDate(n.created_at)} • {n.notification_type}
                      </p>
                    </div>
                  </div>
                  {!n.is_read && (
                    <Button variant="ghost" size="xs" onClick={() => void handleMarkRead(n.id)}>
                      Mark read
                    </Button>
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
