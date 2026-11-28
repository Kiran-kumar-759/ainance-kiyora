import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AppShell } from '../layouts/AppShell';
import { BankCatalogSelector } from '../components/banking/BankCatalogSelector';
import { OnboardingWizard } from '../pages/onboarding/OnboardingWizard';
import { authApi } from '../services/authApi';
import { financeApi } from '../services/financeApi';

let mockOnboardingCompleted = false;

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'newuser@example.in',
      full_name: 'Aarav Mehta',
      is_active: true,
      is_email_verified: true,
      onboarding_completed: mockOnboardingCompleted,
      created_at: '2026-11-28T00:00:00Z',
      last_login_at: null,
    },
    preferences: {
      preferred_currency: 'INR',
      locale: 'en-IN',
      timezone: 'Asia/Kolkata',
      date_format: 'DD/MM/YYYY',
      notification_preferences: { email_alerts: true, bill_reminders: true, monthly_summary: true },
    },
    isAuthenticated: true,
    isLoading: false,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn().mockResolvedValue(undefined),
    updatePreferences: vi.fn(),
  }),
}));

vi.mock('../services/billsApi', () => ({
  billsApi: {
    listNotifications: vi.fn().mockResolvedValue({ items: [], total: 0, unread_count: 0 }),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  },
}));

vi.mock('../services/authApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/authApi')>();
  return {
    ...actual,
    authApi: {
      ...actual.authApi,
      getComprehensiveOnboardingStatus: vi.fn(),
      saveOnboardingProfile: vi.fn(),
      updateOnboarding: vi.fn(),
      selectFinancialSetupMethod: vi.fn(),
      skipFinancialSetup: vi.fn(),
      initializeWorkspace: vi.fn(),
      retryWorkspaceInitialization: vi.fn(),
      getInitializationStatus: vi.fn(),
      completeOnboarding: vi.fn(),
      skipOnboarding: vi.fn(),
    },
  };
});

vi.mock('../services/financeApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/financeApi')>();
  return {
    ...actual,
    financeApi: {
      ...actual.financeApi,
      listBankInstitutions: vi.fn(),
      listAccounts: vi.fn().mockResolvedValue([]),
      createAccount: vi.fn(),
    },
  };
});

describe('First-Time Onboarding, Bank Catalog & Dashboard Gating', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOnboardingCompleted = false;
  });

  it('hides main dashboard sidebar navigation when user onboarding_completed is false', () => {
    mockOnboardingCompleted = false;
    const { rerender } = render(
      <AppShell
        backendReachable={true}
        databaseReady={true}
        isLoading={false}
        onRefresh={vi.fn()}
        currentView="onboarding"
        onNavigate={vi.fn()}
      >
        <div>Onboarding Content</div>
      </AppShell>
    );

    expect(screen.queryByRole('button', { name: /^Dashboard$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Ask AI$/i })).not.toBeInTheDocument();

    mockOnboardingCompleted = true;
    rerender(
      <AppShell
        backendReachable={true}
        databaseReady={true}
        isLoading={false}
        onRefresh={vi.fn()}
        currentView="dashboard"
        onNavigate={vi.fn()}
      >
        <div>Dashboard Content</div>
      </AppShell>
    );

    expect(screen.getByRole('button', { name: /^Dashboard$/i })).toBeInTheDocument();
  });

  it('renders searchable Indian bank catalog and displays honest live-unavailable guidance', async () => {
    vi.mocked(financeApi.listBankInstitutions).mockResolvedValue({
      institutions: [
        {
          bank_id: 'hdfc_bank',
          bank_name: 'HDFC Bank',
          short_name: 'HDFC',
          bank_code: 'HDFC',
          category: 'private_sector',
          logo_key: 'hdfc',
          logo_url: '/assets/banks/hdfc.svg',
          supported_connection_methods: ['statement_import', 'manual_account'],
          provider_id: 'account_aggregator',
          provider_available: false,
          live_supported: false,
          is_demo: false,
          connection_availability_status: 'live_unavailable',
          description: 'HDFC Bank (HDFC)',
          unavailable_reason: 'Live RBI Account Aggregator gateway is not configured in this environment.',
        },
        {
          bank_id: 'demo_national_bank',
          bank_name: 'Demo National Bank of India',
          short_name: 'Demo National Bank of India',
          bank_code: 'DEMO_NATIONAL_BANK',
          category: 'demo',
          logo_key: 'building-2',
          logo_url: '/assets/banks/demo_national_bank.svg',
          supported_connection_methods: ['demo'],
          provider_id: 'demo_national_bank',
          provider_available: true,
          live_supported: false,
          is_demo: true,
          connection_availability_status: 'demo_only',
          description: 'Simulated public sector bank',
          unavailable_reason: null,
        },
      ],
      total: 2,
      live_aa_configured: false,
      demo_available: true,
    });

    const onSelect = vi.fn();
    const onManual = vi.fn();
    render(
      <BankCatalogSelector
        selectedBankId="hdfc_bank"
        onSelectInstitution={onSelect}
        onChooseManualAccount={onManual}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('HDFC Bank')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Search SBI, HDFC/i), {
      target: { value: 'hdfc' },
    });
    expect(screen.getByText('HDFC Bank')).toBeInTheDocument();
    expect(screen.queryByText('Demo National Bank of India')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('HDFC Bank'));
    expect(onSelect).toHaveBeenCalled();
    expect(
      screen.getByText(/Direct Live Account Aggregator Feed Not Configured/i)
    ).toBeInTheDocument();
  });

  it('walks through OnboardingWizard Step 4 setup hub to Step 5 initialization', async () => {
    vi.mocked(authApi.getComprehensiveOnboardingStatus).mockResolvedValue({
      user_id: 'user-1',
      onboarding_completed: false,
      dashboard_access_allowed: false,
      required_gate_view: 'onboarding',
      is_email_verified: true,
      current_stage: 'financial_data_setup',
      completed_stages: ['registered', 'profile_setup'],
      current_step: 4,
      profile_completed: true,
      profile: {
        first_name: 'Aarav',
        last_name: 'Mehta',
        full_name: 'Aarav Mehta',
        email: 'newuser@example.in',
        country: 'India',
        financial_year: 'April-March',
        financial_goals: ['Emergency Fund'],
      },
      financial_setup_status: 'not_started',
      financial_setup_skipped: false,
      has_active_banking_connection: false,
      accounts_count: 0,
      transactions_count: 0,
      pending_import_batches_count: 0,
      pending_documents_count: 0,
      initialization_status: 'not_started',
      initialization_steps: [],
      next_action: 'choose_financial_setup',
      guidance_message: 'Choose a setup method.',
      preferences: {
        preferred_currency: 'INR',
        locale: 'en-IN',
        timezone: 'Asia/Kolkata',
        date_format: 'DD/MM/YYYY',
        notification_preferences: {},
      },
    });
    vi.mocked(financeApi.listBankInstitutions).mockResolvedValue({
      institutions: [],
      total: 0,
      live_aa_configured: false,
      demo_available: true,
    });
    vi.mocked(authApi.updateOnboarding).mockResolvedValue({
      onboarding_completed: false,
      is_email_verified: true,
      full_name: 'Aarav Mehta',
      current_step: 5,
      preferences: {
        preferred_currency: 'INR',
        locale: 'en-IN',
        timezone: 'Asia/Kolkata',
        date_format: 'DD/MM/YYYY',
        notification_preferences: {},
      },
    });
    vi.mocked(authApi.initializeWorkspace).mockResolvedValue({
      initialization_status: 'completed',
      steps: [
        {
          key: 'preparing_workspace',
          label: 'Preparing your financial workspace',
          status: 'completed',
          detail: 'Categories ready.',
        },
        {
          key: 'workspace_ready',
          label: 'Your financial workspace is ready',
          status: 'completed',
          detail: 'Dashboard activated.',
        },
      ],
      dashboard_access_allowed: true,
      onboarding_completed: true,
      current_stage: 'completed',
      summary: { accounts_verified: 0, transactions_count: 0 },
    });

    const onComplete = vi.fn();
    render(<OnboardingWizard onComplete={onComplete} />);

    await waitFor(() => {
      expect(screen.getByText(/Set Up Your Financial Data/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Connect Bank/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Add Account/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Import CSV\/XLSX/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Upload Receipt/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^Continue$/i }));

    await waitFor(() => {
      expect(authApi.initializeWorkspace).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Preparing your financial workspace/i)).toBeInTheDocument();
      expect(screen.getByText(/You're All Set!/i)).toBeInTheDocument();
    });
  });
});
