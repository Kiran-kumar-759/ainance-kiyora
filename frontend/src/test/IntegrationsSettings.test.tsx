import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { IntegrationsPage } from '../pages/integrations/IntegrationsPage';
import { SettingsPage } from '../pages/settings/SettingsPage';
import { AppShell } from '../layouts/AppShell';
import { integrationsApi } from '../services/integrationsApi';
import { assistantApi } from '../services/assistantApi';
import { authApi } from '../services/authApi';
import { emailIngestionApi } from '../services/documentsApi';
import { billsApi } from '../services/billsApi';

const mockUpdatePreferences = vi.fn();
const mockRefreshUser = vi.fn();
const mockLogout = vi.fn();

const mockUser = {
  id: 'u-1',
  email: 'kiran@example.in',
  full_name: 'Kiran Kumar',
  is_active: true,
  is_email_verified: true,
  onboarding_completed: true,
  created_at: '2026-10-01T10:00:00Z',
  last_login_at: '2026-11-26T06:00:00Z',
};

const mockUserPrefs = {
  preferred_currency: 'INR',
  locale: 'en-IN',
  timezone: 'Asia/Kolkata',
  date_format: 'DD/MM/YYYY',
  notification_preferences: {
    email_alerts: true,
    bill_reminders: true,
    subscription_reminders: true,
    loan_emi_reminders: true,
    payment_due_reminders: true,
    financial_insights: true,
    spending_anomalies: true,
    forecast_notifications: true,
    monthly_summary: true,
    email_reminders_enabled: true,
    sms_reminders_enabled: false,
    week_start: 'monday' as const,
    language: 'en-IN',
    default_landing_view: 'dashboard' as const,
    compact_sidebar: false,
  },
};

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    preferences: mockUserPrefs,
    isAuthenticated: true,
    isLoading: false,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: mockLogout,
    refreshUser: mockRefreshUser,
    updatePreferences: mockUpdatePreferences,
  }),
}));

vi.mock('../services/integrationsApi', () => ({
  integrationsApi: {
    getOverview: vi.fn(),
    listProviders: vi.fn(),
    getProvider: vi.fn(),
    testProvider: vi.fn(),
    listConnections: vi.fn(),
    disconnectConnection: vi.fn(),
  },
}));

vi.mock('../services/assistantApi', () => ({
  assistantApi: {
    listProviders: vi.fn(),
    getPreferences: vi.fn(),
    updatePreferences: vi.fn(),
  },
}));

vi.mock('../services/authApi', () => ({
  authApi: {
    updateProfile: vi.fn(),
    resendVerification: vi.fn(),
    changePassword: vi.fn(),
    listSessions: vi.fn(),
    revokeSession: vi.fn(),
    logoutAll: vi.fn(),
    getPrivacySummary: vi.fn(),
  },
}));

vi.mock('../services/documentsApi', () => ({
  emailIngestionApi: {
    getGmailConnectUrl: vi.fn(),
  },
}));

vi.mock('../services/billsApi', () => ({
  billsApi: {
    listNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  },
}));

const sampleOverview = {
  total_integrations: 9,
  configured_count: 3,
  connected_count: 1,
  unavailable_count: 6,
  attention_required_count: 0,
  planned_count: 1,
  preferred_web_provider: 'tavily' as const,
  web_search_enabled: true,
  integrations: [
    {
      provider_id: 'tavily',
      name: 'Tavily',
      category: 'web_research' as const,
      description: 'AI-ready financial search',
      status: 'available' as const,
      configured: true,
      connected: true,
      available: true,
      is_planned: false,
      is_preferred: true,
      can_test: true,
      can_connect: false,
      can_disconnect: false,
      capabilities: ['External Financial Web Search'],
      required_env_vars: [],
      last_sync_or_test_at: null,
      last_error: null,
      safe_metadata: { supports_full_text: true },
    },
    {
      provider_id: 'langsearch',
      name: 'LangSearch',
      category: 'web_research' as const,
      description: 'Structured web search snippets',
      status: 'unavailable' as const,
      configured: false,
      connected: false,
      available: false,
      is_planned: false,
      is_preferred: false,
      can_test: true,
      can_connect: false,
      can_disconnect: false,
      capabilities: ['External Financial Web Search'],
      required_env_vars: ['LANGSEARCH_API_KEY'],
      last_sync_or_test_at: null,
      last_error: null,
      safe_metadata: { supports_full_text: true },
    },
    {
      provider_id: 'smtp',
      name: 'SMTP Outbound Email',
      category: 'notifications' as const,
      description: 'SMTP notification relay',
      status: 'unavailable' as const,
      configured: false,
      connected: false,
      available: false,
      is_planned: false,
      is_preferred: false,
      can_test: true,
      can_connect: false,
      can_disconnect: false,
      capabilities: ['Email Reminders'],
      required_env_vars: ['SMTP_ENABLED', 'SMTP_HOST'],
      last_sync_or_test_at: null,
      last_error: 'SMTP_ENABLED=false',
      safe_metadata: { smtp_enabled: false, sender_address: 'support@personalfinancemanager.in' },
    },
  ],
  connections: [
    {
      connection_id: 'conn-gmail-1',
      connection_type: 'email' as const,
      provider_id: 'gmail',
      display_name: 'Gmail OAuth (Read-Only)',
      status: 'connected',
      account_or_email: 'kiran@gmail.com',
      linked_accounts_count: 0,
      scopes: ['https://www.googleapis.com/auth/gmail.readonly'],
      token_expires_at: null,
      last_sync_at: '2026-11-26T05:00:00Z',
      last_error: null,
      can_disconnect: true,
    },
  ],
};

describe('Pre-Phase 12 Integrations & Settings Centers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(integrationsApi.getOverview).mockResolvedValue(sampleOverview);
    vi.mocked(assistantApi.getPreferences).mockResolvedValue({
      default_web_provider: 'tavily',
      web_search_enabled: true,
      voice_read_aloud_enabled: false,
      auto_execute_actions: false,
      updated_at: '2026-11-26T00:00:00Z',
    });
    vi.mocked(assistantApi.listProviders).mockResolvedValue([
      {
        provider: 'tavily',
        display_name: 'Tavily',
        description: 'Tavily search',
        configured: true,
        supports_full_text: true,
      },
      {
        provider: 'langsearch',
        display_name: 'LangSearch',
        description: 'LangSearch search',
        configured: false,
        supports_full_text: true,
      },
      {
        provider: 'firecrawl',
        display_name: 'Firecrawl',
        description: 'Firecrawl scrape',
        configured: false,
        supports_full_text: true,
      },
    ]);
    vi.mocked(billsApi.listNotifications).mockResolvedValue({
      items: [],
      total: 0,
      unread_count: 0,
    });
  });

  it('renders Integrations Center KPIs, updates preferred web provider, and executes provider test', async () => {
    vi.mocked(assistantApi.updatePreferences).mockResolvedValue({
      default_web_provider: 'langsearch',
      web_search_enabled: true,
      voice_read_aloud_enabled: false,
      auto_execute_actions: false,
      updated_at: '2026-11-26T00:01:00Z',
    });
    vi.mocked(integrationsApi.testProvider).mockResolvedValue({
      provider_id: 'tavily',
      status: 'ok',
      success: true,
      message: 'Tavily responded cleanly (2 search result(s)).',
      latency_ms: 85,
      checked_at: '2026-11-26T00:01:00Z',
      details: { no_silent_fallback: true },
    });

    const onNavigate = vi.fn();
    render(<IntegrationsPage onNavigate={onNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('Integrations Center')).toBeInTheDocument();
      expect(screen.getByText('Available Integrations')).toBeInTheDocument();
      expect(screen.getByText('kiran@gmail.com', { exact: false })).toBeInTheDocument();
    });

    const selectButtons = screen.getAllByRole('button', { name: /Select Provider/i });
    fireEvent.click(selectButtons[0]);

    await waitFor(() => {
      expect(assistantApi.updatePreferences).toHaveBeenCalledWith({
        default_web_provider: 'langsearch',
      });
    });

    const testButtons = screen.getAllByRole('button', { name: /Test Connection/i });
    fireEvent.click(testButtons[0]);

    await waitFor(() => {
      expect(integrationsApi.testProvider).toHaveBeenCalledWith('tavily');
      expect(
        screen.getAllByText(/Tavily responded cleanly \(2 search result\(s\)\)/i).length
      ).toBeGreaterThan(0);
    });
  });

  it('navigates Settings tabs, validates password confirmation, saves profile & privacy summary', async () => {
    vi.mocked(authApi.updateProfile).mockResolvedValue({
      ...mockUser,
      full_name: 'Kiran Updated',
    });
    vi.mocked(authApi.listSessions).mockResolvedValue([
      {
        id: 'sess-1',
        created_at: '2026-11-26T01:00:00Z',
        expires_at: '2026-12-03T01:00:00Z',
        last_used_at: '2026-11-26T06:00:00Z',
        user_agent: 'Mozilla/5.0 Linux',
        ip_address: '127.0.0.1',
        is_current: true,
      },
    ]);
    vi.mocked(authApi.changePassword).mockResolvedValue({
      message: 'Password updated successfully.',
    });
    vi.mocked(authApi.getPrivacySummary).mockResolvedValue({
      accounts_count: 3,
      transactions_count: 42,
      bills_count: 5,
      subscriptions_count: 2,
      loans_count: 1,
      documents_count: 4,
      conversations_count: 2,
      forecast_scenarios_count: 1,
      banking_connections_count: 1,
      email_connections_count: 1,
      data_storage_disclosures: ['Stored privately in PostgreSQL'],
      export_endpoints: [
        {
          label: 'Transactions Ledger CSV',
          endpoint: '/api/v1/reports/transactions.csv',
          description: 'Formula-safe CSV',
        },
      ],
      account_deletion_status: 'deferred',
      account_deletion_note: 'Account deletion is deferred cleanly.',
    });

    render(<SettingsPage onNavigate={vi.fn()} />);

    // 1. Profile edit
    const nameInput = screen.getByLabelText(/Display Name/i);
    fireEvent.change(nameInput, { target: { value: 'Kiran Updated' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Profile/i }));
    await waitFor(() => {
      expect(authApi.updateProfile).toHaveBeenCalledWith('Kiran Updated');
    });

    // 2. Security tab -> sessions + change password
    fireEvent.click(screen.getByRole('tab', { name: /Security & Sessions/i }));
    await waitFor(() => {
      expect(authApi.listSessions).toHaveBeenCalled();
      expect(screen.getByText(/Current Session/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Current Password/i), {
      target: { value: 'OldPass123!' },
    });
    fireEvent.change(screen.getByLabelText(/^New Password$/i), {
      target: { value: 'NewStrongPass456!' },
    });
    fireEvent.change(screen.getByLabelText(/Confirm New Password/i), {
      target: { value: 'NewStrongPass456!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Update Password/i }));
    await waitFor(() => {
      expect(authApi.changePassword).toHaveBeenCalledWith('OldPass123!', 'NewStrongPass456!', true);
    });

    // 3. Privacy & Data tab
    fireEvent.click(screen.getByRole('tab', { name: /Privacy & Data/i }));
    await waitFor(() => {
      expect(authApi.getPrivacySummary).toHaveBeenCalled();
      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText(/Account Deletion Status: Deferred/i)).toBeInTheDocument();
    });
  });

  it('activates clickable Integrations and Settings sidebar navigation in AppShell', () => {
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
        <div>Child Content</div>
      </AppShell>
    );

    const integBtn = screen.getByRole('button', { name: /^Integrations$/i });
    const settingsBtn = screen.getByRole('button', { name: /^Settings$/i });
    expect(integBtn).toBeEnabled();
    expect(settingsBtn).toBeEnabled();

    fireEvent.click(integBtn);
    expect(onNavigate).toHaveBeenCalledWith('integrations');
    fireEvent.click(settingsBtn);
    expect(onNavigate).toHaveBeenCalledWith('settings');

    // Keep unused import check clean
    expect(emailIngestionApi.getGmailConnectUrl).toBeDefined();
  });
});
