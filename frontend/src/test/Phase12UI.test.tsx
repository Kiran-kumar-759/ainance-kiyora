import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LandingPage } from '../pages/landing/LandingPage';
import { RemindersPage } from '../pages/reminders/RemindersPage';
import { AppShell } from '../layouts/AppShell';
import { ToastProvider } from '../components/ui/ToastProvider';
import { billsApi } from '../services/billsApi';
import { loansApi, subscriptionsApi } from '../services/phase6Api';
import { emailIngestionApi } from '../services/documentsApi';
import { integrationsApi } from '../services/integrationsApi';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'kiran@example.in',
      full_name: 'Kiran Kumar',
      is_email_verified: true,
      onboarding_completed: true,
    },
    preferences: {
      preferred_currency: 'INR',
      locale: 'en-IN',
      timezone: 'Asia/Kolkata',
      date_format: 'DD/MM/YYYY',
      notification_preferences: {
        bill_reminders: true,
        emi_reminders: true,
        compact_sidebar: false,
      },
    },
    isAuthenticated: true,
    isLoading: false,
    logout: vi.fn(),
    refreshUser: vi.fn(),
    updatePreferences: vi.fn(),
  }),
}));

vi.mock('../services/billsApi', () => ({
  billsApi: {
    listBills: vi.fn(),
    listNotifications: vi.fn(),
    processReminders: vi.fn(),
    updateReminders: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  },
}));

vi.mock('../services/phase6Api', () => ({
  subscriptionsApi: {
    listSubscriptions: vi.fn(),
    updateSubscription: vi.fn(),
  },
  loansApi: {
    listLoans: vi.fn(),
    updateLoan: vi.fn(),
  },
}));

vi.mock('../services/documentsApi', () => ({
  emailIngestionApi: {
    getConnections: vi.fn(),
  },
}));

vi.mock('../services/integrationsApi', () => ({
  integrationsApi: {
    getProvider: vi.fn(),
    testProvider: vi.fn(),
  },
}));

describe('Phase 12 Frontend Transformation & Reminders Module', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders LandingPage hero, CTAs, sample disclaimer, and live platform readiness', () => {
    const onNavigate = vi.fn();
    render(
      <LandingPage
        health={{ status: 'ok', app: 'FinSight AI', environment: 'development', version: '1.0.0', timestamp: '2026-11-26T00:00:00Z' }}
        readiness={{
          status: 'ready',
          database: { ready: true, status: 'connected', database_name: 'pfm_dev', latency_ms: 1.8, error: null },
          environment: 'development',
          timestamp: '2026-11-26T00:00:00Z',
        }}
        platform={{
          app_name: 'AI Personal Finance Manager',
          version: '1.0.0',
          phase: 'Phase 12',
          target_market: 'India',
          primary_currency: 'INR',
          fiscal_year_cycle: 'April - March',
          environment: 'development',
          database_connected: true,
          database_name: 'pfm_dev',
          settings_count: 1,
          timestamp: '2026-11-26T00:00:00Z',
        }}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
        onNavigate={onNavigate}
        isAuthenticated={false}
      />
    );

    expect(screen.getByText(/Take Control of Your Money/i)).toBeInTheDocument();
    expect(screen.getByText(/Sample Preview Only/i)).toBeInTheDocument();
    expect(screen.getByText(/Ready \(1.8 ms\)/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^Login$/i }));
    expect(onNavigate).toHaveBeenCalledWith('login');

    fireEvent.click(screen.getByRole('button', { name: /^Get Started$/i }));
    expect(onNavigate).toHaveBeenCalledWith('register');
  });

  it('navigates cleanly to Reminders & Notifications from AppShell sidebar and supports collapsing', () => {
    const onNavigate = vi.fn();
    render(
      <AppShell
        backendReachable={true}
        databaseReady={true}
        isLoading={false}
        onRefresh={vi.fn()}
        currentView="dashboard"
        onNavigate={onNavigate}
      >
        <div>Workspace Content</div>
      </AppShell>
    );

    const remindersBtn = screen.getByRole('button', { name: /^Reminders & Notifications$/i });
    fireEvent.click(remindersBtn);
    expect(onNavigate).toHaveBeenCalledWith('reminders');

    const collapseBtn = screen.getByRole('button', { name: /Collapse sidebar/i });
    fireEvent.click(collapseBtn);
    expect(screen.getByRole('button', { name: /Expand sidebar/i })).toBeInTheDocument();
  });

  it('renders RemindersPage with commitment toggles, inbound Gmail vs SMTP separation, due dispatch & honest composer gap notice', async () => {
    vi.mocked(billsApi.listBills).mockResolvedValue({
      items: [
        {
          id: 'bill-1',
          bill_name: 'BESCOM Electricity',
          bill_category: 'electricity',
          bill_type: 'recurring',
          due_date: '2026-12-02',
          expected_amount: '1200.00',
          status: 'upcoming',
          derived_status: 'upcoming',
          reminder_enabled: true,
          reminder_days_before: [3, 1, 0],
          notification_channels: { in_app: true, email: true, sms: false },
          reminders: [
            {
              id: 'rem-1',
              bill_id: 'bill-1',
              offset_days: 3,
              reminder_at: '2026-11-29T09:00:00Z',
              channels: ['in_app', 'email'],
              is_enabled: true,
              delivery_status: 'scheduled',
              channel_outcomes: {},
              retry_count: 0,
              max_retries: 3,
              idempotency_key: 'k1',
            },
          ],
        } as never,
      ],
      total: 1,
      page: 1,
      page_size: 100,
      total_pages: 1,
    });
    vi.mocked(subscriptionsApi.listSubscriptions).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 100,
      total_pages: 1,
    });
    vi.mocked(loansApi.listLoans).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 100,
      total_pages: 1,
    });
    vi.mocked(billsApi.listNotifications).mockResolvedValue({
      items: [],
      total: 0,
      unread_count: 0,
    });
    vi.mocked(integrationsApi.getProvider).mockResolvedValue({
      provider_id: 'smtp',
      name: 'SMTP Outbound Email',
      category: 'notifications',
      description: 'SMTP relay configured for reminders.',
      status: 'available',
      configured: true,
      connected: false,
      available: true,
      is_planned: false,
      is_preferred: false,
      can_test: true,
      can_connect: false,
      can_disconnect: false,
      capabilities: ['email'],
      required_env_vars: ['SMTP_HOST'],
      last_sync_or_test_at: null,
      last_error: null,
      safe_metadata: {},
    });
    vi.mocked(emailIngestionApi.getConnections).mockResolvedValue([
      {
        id: 'conn-1',
        provider: 'gmail',
        email_address: 'kiran@gmail.com',
        status: 'active',
        created_at: '2026-11-25T00:00:00Z',
      } as never,
    ]);
    vi.mocked(billsApi.processReminders).mockResolvedValue({
      processed_count: 1,
      delivered_count: 1,
      partial_count: 0,
      unavailable_count: 0,
      failed_count: 0,
      notifications_created: 1,
      email_configured: true,
      sms_configured: false,
    });

    render(
      <ToastProvider>
        <RemindersPage onNavigate={vi.fn()} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('BESCOM Electricity')).toBeInTheDocument();
    });

    expect(screen.getByText(/Outbound Email Channel \(SMTP\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Inbound Bill Ingestion \(Gmail OAuth — Read-Only\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Backend Endpoint Unavailable/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Evaluate & Dispatch Due Reminders/i }));
    await waitFor(() => {
      expect(billsApi.processReminders).toHaveBeenCalledTimes(1);
    });
  });

  it('resolves individual page URLs, preserves deep-link filters, and syncs browser History cleanly', async () => {
    const { getPathForView, getViewFromLocation, syncBrowserUrl } = await import('../lib/routes');

    expect(getPathForView('foundation')).toBe('/');
    expect(getPathForView('bills')).toBe('/bills');
    expect(getPathForView('reminders')).toBe('/reminders');
    expect(getPathForView('assistant')).toBe('/assistant');

    const txUrl = getPathForView('transactions', {
      categoryId: 'cat-food',
      transactionType: 'expense',
    });
    expect(txUrl).toBe('/transactions?categoryId=cat-food&type=expense');

    const parsedTx = getViewFromLocation('/transactions', '?categoryId=cat-food&type=expense');
    expect(parsedTx.view).toBe('transactions');
    expect(parsedTx.txFilters).toEqual({
      categoryId: 'cat-food',
      transactionType: 'expense',
    });

    const parsedReset = getViewFromLocation('/', '?token=abc123&action=reset-password');
    expect(parsedReset.view).toBe('reset-password');
    expect(parsedReset.token).toBe('abc123');

    syncBrowserUrl('bills');
    expect(window.location.pathname).toBe('/bills');
    expect(getViewFromLocation().view).toBe('bills');

    // Cleanly restore root URL for downstream tests
    syncBrowserUrl('foundation', { replace: true });
    expect(window.location.pathname).toBe('/');
  });
});
