import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DashboardPage } from '../pages/finance/DashboardPage';
import { AccountsPage } from '../pages/finance/AccountsPage';
import { TransactionsPage } from '../pages/finance/TransactionsPage';
import { TransfersPage } from '../pages/finance/TransfersPage';
import { BankingPage } from '../pages/banking/BankingPage';
import { financeApi } from '../services/financeApi';

vi.mock('../services/financeApi', () => ({
  financeApi: {
    getDashboard: vi.fn(),
    listAccounts: vi.fn(),
    createAccount: vi.fn(),
    updateAccount: vi.fn(),
    updateOpeningBalance: vi.fn(),
    archiveAccount: vi.fn(),
    restoreAccount: vi.fn(),
    getAccountsSummary: vi.fn(),
    listCategories: vi.fn(),
    createCategory: vi.fn(),
    deleteCategory: vi.fn(),
    listTransactions: vi.fn(),
    createTransaction: vi.fn(),
    updateTransaction: vi.fn(),
    deleteTransaction: vi.fn(),
    listTransfers: vi.fn(),
    executeTransfer: vi.fn(),
    reverseTransfer: vi.fn(),
    listBankingProviders: vi.fn(),
    listBankingConnections: vi.fn(),
    connectDemoProvider: vi.fn(),
    discoverBankingAccounts: vi.fn(),
    importBankingAccounts: vi.fn(),
    syncBankingConnection: vi.fn(),
    listBankingSyncRuns: vi.fn(),
    disconnectBankingConnection: vi.fn(),
  },
}));

describe('Frontend Financial Engine & Banking Pages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders dashboard with net financial position, assets, and liabilities in INR', async () => {
    const onNavigate = vi.fn();
    vi.mocked(financeApi.getDashboard).mockResolvedValue({
      total_assets: '150000.00',
      total_liabilities: '25000.00',
      net_financial_position: '125000.00',
      account_count: 3,
      period: 'this_month',
      period_start: '2026-11-01',
      period_end: '2026-11-30',
      total_income: '85000.00',
      total_expenses: '32000.00',
      net_savings: '53000.00',
      savings_rate_pct: '62.35',
      recent_transactions: [
        {
          id: 'tx-1',
          user_id: 'u-1',
          account_id: 'a-1',
          account_name: 'HDFC Salary',
          transaction_type: 'income',
          amount: '85000.00',
          currency: 'INR',
          description: 'Tech Salary Credit',
          transaction_date: '2026-11-01',
          source: 'manual',
          created_at: '2026-11-01T10:00:00Z',
          updated_at: '2026-11-01T10:00:00Z',
        },
      ],
      accounts: [
        {
          id: 'a-1',
          user_id: 'u-1',
          name: 'HDFC Salary',
          account_type: 'savings',
          currency: 'INR',
          opening_balance: '65000.00',
          current_balance: '150000.00',
          status: 'active',
          source: 'manual',
          created_at: '2026-11-01T00:00:00Z',
          updated_at: '2026-11-01T00:00:00Z',
        },
      ],
    });

    render(<DashboardPage onNavigate={onNavigate} />);

    expect(screen.getByText('Financial Overview')).toBeInTheDocument();

    await waitFor(() => {
      // Formatted in Indian Rupee format
      expect(screen.getByText('₹1,25,000.00')).toBeInTheDocument();
      expect(screen.getAllByText('₹1,50,000.00').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('₹25,000.00')).toBeInTheDocument();
      expect(screen.getByText('Tech Salary Credit')).toBeInTheDocument();
    });
  });

  it('renders accounts page, lists accounts, and handles create account', async () => {
    const onNavigate = vi.fn();
    vi.mocked(financeApi.listAccounts).mockResolvedValue([
      {
        id: 'acc-101',
        user_id: 'u-1',
        name: 'ICICI Savings',
        account_type: 'savings',
        institution_name: 'ICICI Bank',
        account_identifier: '••4821',
        currency: 'INR',
        opening_balance: '25000.00',
        current_balance: '25000.00',
        status: 'active',
        source: 'manual',
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.createAccount).mockResolvedValue({
      id: 'acc-102',
      user_id: 'u-1',
      name: 'Cash in Hand',
      account_type: 'cash',
      currency: 'INR',
      opening_balance: '5000.00',
      current_balance: '5000.00',
      status: 'active',
      source: 'manual',
      created_at: '2026-11-01T00:00:00Z',
      updated_at: '2026-11-01T00:00:00Z',
    });

    render(<AccountsPage onNavigate={onNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('ICICI Savings')).toBeInTheDocument();
      expect(screen.getByText('ICICI Bank')).toBeInTheDocument();
      expect(screen.getByText('₹25,000.00')).toBeInTheDocument();
    });

    // Open Add Account Modal
    fireEvent.click(screen.getByText('Add Account'));
    expect(screen.getByText('Create Financial Account')).toBeInTheDocument();

    // Fill form
    fireEvent.change(screen.getByPlaceholderText('e.g. HDFC Salary, ICICI Savings, Cash Wallet'), {
      target: { value: 'Cash in Hand' },
    });
    fireEvent.click(screen.getByText('Save Account'));

    await waitFor(() => {
      expect(financeApi.createAccount).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Cash in Hand',
          account_type: 'savings',
          currency: 'INR',
        })
      );
    });
  });

  it('renders transactions page, filters, and records new transaction', async () => {
    const onNavigate = vi.fn();
    vi.mocked(financeApi.listAccounts).mockResolvedValue([
      {
        id: 'acc-1',
        user_id: 'u-1',
        name: 'HDFC Salary',
        account_type: 'savings',
        currency: 'INR',
        opening_balance: '10000.00',
        current_balance: '10000.00',
        status: 'active',
        source: 'manual',
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.listCategories).mockResolvedValue([
      {
        id: 'cat-1',
        name: 'Groceries',
        category_type: 'expense',
        is_system: true,
        created_at: '2026-11-01T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.listTransactions).mockResolvedValue({
      items: [
        {
          id: 'tx-99',
          user_id: 'u-1',
          account_id: 'acc-1',
          account_name: 'HDFC Salary',
          transaction_type: 'expense',
          amount: '1250.00',
          currency: 'INR',
          category_id: 'cat-1',
          category_name: 'Groceries',
          description: 'Vegetables & Milk',
          merchant_payee: 'Nature Basket',
          transaction_date: '2026-11-12',
          source: 'manual',
          created_at: '2026-11-12T10:00:00Z',
          updated_at: '2026-11-12T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 15,
      total_pages: 1,
    });
    vi.mocked(financeApi.createTransaction).mockResolvedValue({
      id: 'tx-100',
      user_id: 'u-1',
      account_id: 'acc-1',
      transaction_type: 'expense',
      amount: '500.00',
      currency: 'INR',
      description: 'Coffee',
      transaction_date: '2026-11-15',
      source: 'manual',
      created_at: '2026-11-15T00:00:00Z',
      updated_at: '2026-11-15T00:00:00Z',
    });

    render(<TransactionsPage onNavigate={onNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('Vegetables & Milk')).toBeInTheDocument();
      expect(screen.getByText('Nature Basket')).toBeInTheDocument();
      expect(screen.getByText('-₹1,250.00')).toBeInTheDocument();
    });

    // Open Record Transaction modal
    fireEvent.click(screen.getByText('Record Transaction'));
    expect(screen.getByText('Record Financial Transaction')).toBeInTheDocument();

    // Fill form
    fireEvent.change(screen.getByPlaceholderText('0.00'), {
      target: { value: '500.00' },
    });
    fireEvent.change(screen.getByPlaceholderText('e.g. Swiggy food delivery, Salary credit'), {
      target: { value: 'Coffee' },
    });
    fireEvent.click(screen.getByText('Save Transaction'));

    await waitFor(() => {
      expect(financeApi.createTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          account_id: 'acc-1',
          transaction_type: 'expense',
          amount: '500.00',
          description: 'Coffee',
        })
      );
    });
  });

  it('renders transfers page, validates accounts, and executes fund transfer', async () => {
    const onNavigate = vi.fn();
    vi.mocked(financeApi.listAccounts).mockResolvedValue([
      {
        id: 'acc-src',
        user_id: 'u-1',
        name: 'Savings A',
        account_type: 'savings',
        currency: 'INR',
        opening_balance: '20000.00',
        current_balance: '20000.00',
        status: 'active',
        source: 'manual',
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
      {
        id: 'acc-dest',
        user_id: 'u-1',
        name: 'Wallet B',
        account_type: 'digital_wallet',
        currency: 'INR',
        opening_balance: '1000.00',
        current_balance: '1000.00',
        status: 'active',
        source: 'manual',
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.listTransfers).mockResolvedValue([
      {
        id: 'tr-1',
        user_id: 'u-1',
        source_account_id: 'acc-src',
        source_account_name: 'Savings A',
        destination_account_id: 'acc-dest',
        destination_account_name: 'Wallet B',
        amount: '3000.00',
        currency: 'INR',
        transfer_date: '2026-11-10',
        description: 'Wallet top-up',
        status: 'completed',
        created_at: '2026-11-10T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.executeTransfer).mockResolvedValue({
      id: 'tr-2',
      user_id: 'u-1',
      source_account_id: 'acc-src',
      source_account_name: 'Savings A',
      destination_account_id: 'acc-dest',
      destination_account_name: 'Wallet B',
      amount: '2000.00',
      currency: 'INR',
      transfer_date: '2026-11-15',
      status: 'completed',
      created_at: '2026-11-15T00:00:00Z',
    });

    render(<TransfersPage onNavigate={onNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('Savings A → Wallet B')).toBeInTheDocument();
      expect(screen.getByText('₹3,000.00')).toBeInTheDocument();
    });

    // Execute transfer
    fireEvent.change(screen.getByPlaceholderText('0.00'), {
      target: { value: '2000.00' },
    });
    fireEvent.click(screen.getByText('Transfer Funds'));

    await waitFor(() => {
      expect(financeApi.executeTransfer).toHaveBeenCalledWith(
        expect.objectContaining({
          source_account_id: 'acc-src',
          destination_account_id: 'acc-dest',
          amount: '2000.00',
        })
      );
    });
  });

  it('renders simulated banking page, displays disclaimer, and requires consent', async () => {
    const onNavigate = vi.fn();
    vi.mocked(financeApi.listBankingProviders).mockResolvedValue([
      {
        provider_id: 'demo_national_bank',
        name: 'Demo National Bank of India',
        description: 'Simulated PSU bank.',
        is_simulated: true,
        logo_key: 'building-2',
        supported_account_types: ['savings', 'current'],
      },
    ]);
    vi.mocked(financeApi.listBankingConnections).mockResolvedValue([]);
    vi.mocked(financeApi.connectDemoProvider).mockResolvedValue({
      id: 'conn-1',
      provider_id: 'demo_national_bank',
      institution_name: 'Demo National Bank of India',
      status: 'connected',
      consent_granted_at: '2026-11-15T00:00:00Z',
      is_simulated: true,
      created_at: '2026-11-15T00:00:00Z',
      connected_accounts_count: 0,
    });

    render(<BankingPage onNavigate={onNavigate} />);

    // Verify simulation disclaimer is shown
    expect(
      screen.getByText('Simulated Indian Banking Environment')
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText('Demo National Bank of India')
      ).toBeInTheDocument();
      expect(screen.getByText('Simulated PSU bank.')).toBeInTheDocument();
    });

    // Click Connect Simulation
    fireEvent.click(screen.getByText('Connect Simulation'));
    expect(
      screen.getByText('Connect Demo National Bank of India')
    ).toBeInTheDocument();

    // Authorize button disabled before consent
    const authBtn = screen.getByRole('button', { name: /Authorize & Connect/i });
    expect(authBtn).toBeDisabled();

    // Check consent checkbox
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    expect(authBtn).not.toBeDisabled();

    // Submit
    fireEvent.click(authBtn);
    await waitFor(() => {
      expect(financeApi.connectDemoProvider).toHaveBeenCalledWith(
        'demo_national_bank',
        true
      );
    });
  });

  it('handles account creation errors cleanly and shows confirmed success banner', async () => {
    const onNavigate = vi.fn();
    vi.mocked(financeApi.listAccounts).mockResolvedValue([]);
    vi.mocked(financeApi.createAccount).mockRejectedValueOnce(
      new Error('An active savings account named "SBI Savings" already exists.')
    );

    render(<AccountsPage onNavigate={onNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('No accounts found')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Add Account'));
    fireEvent.change(screen.getByPlaceholderText('e.g. HDFC Salary, ICICI Savings, Cash Wallet'), {
      target: { value: 'SBI Savings' },
    });
    fireEvent.click(screen.getByText('Save Account'));

    await waitFor(() => {
      expect(
        screen.getByText('An active savings account named "SBI Savings" already exists.')
      ).toBeInTheDocument();
    });
    // Modal remains open and Save button is re-enabled (not stuck loading)
    expect(screen.getByText('Save Account')).not.toBeDisabled();

    // Retry succeeds
    vi.mocked(financeApi.createAccount).mockResolvedValueOnce({
      id: 'acc-201',
      user_id: 'u-1',
      name: 'SBI Savings',
      account_type: 'savings',
      institution_name: 'SBI',
      currency: 'INR',
      opening_balance: '25000.00',
      current_balance: '25000.00',
      status: 'active',
      source: 'manual',
      created_at: '2026-11-25T00:00:00Z',
      updated_at: '2026-11-25T00:00:00Z',
    });

    fireEvent.click(screen.getByText('Save Account'));
    await waitFor(() => {
      expect(
        screen.getByText('Account "SBI Savings" created with balance ₹25,000.00.')
      ).toBeInTheDocument();
    });
  });

  it('supports demo banking discovery, selective import, sync, sync history, and inline errors without alert', async () => {
    const onNavigate = vi.fn();
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

    vi.mocked(financeApi.listBankingProviders).mockResolvedValue([
      {
        provider_id: 'demo_national_bank',
        name: 'Demo National Bank of India',
        description: 'PSU simulation',
        is_simulated: true,
        logo_key: 'building-2',
        supported_account_types: ['savings', 'current'],
      },
    ]);
    vi.mocked(financeApi.listBankingConnections).mockResolvedValue([
      {
        id: 'conn-1',
        provider_id: 'demo_national_bank',
        institution_name: 'Demo National Bank of India',
        status: 'connected',
        consent_granted_at: '2026-11-25T00:00:00Z',
        is_simulated: true,
        created_at: '2026-11-25T00:00:00Z',
        connected_accounts_count: 1,
      },
    ]);
    vi.mocked(financeApi.discoverBankingAccounts).mockResolvedValue([
      {
        external_account_id: 'dnb_sav_001',
        name: 'DNB Salary Savings Account',
        account_type: 'savings',
        institution_name: 'Demo National Bank of India',
        masked_account_number: '••• 4892',
        balance: '125450.00',
        currency: 'INR',
        already_imported: false,
      },
    ]);
    vi.mocked(financeApi.importBankingAccounts).mockResolvedValue([
      {
        id: 'acc-demo-1',
        user_id: 'u-1',
        name: 'DNB Salary Savings Account',
        account_type: 'savings',
        institution_name: 'Demo National Bank of India',
        account_identifier: '••• 4892',
        currency: 'INR',
        opening_balance: '125450.00',
        current_balance: '125450.00',
        status: 'active',
        source: 'demo_bank',
        created_at: '2026-11-25T00:00:00Z',
        updated_at: '2026-11-25T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.syncBankingConnection).mockResolvedValue({
      connection_id: 'conn-1',
      status: 'success',
      accounts_synced: 1,
      transactions_synced: 4,
      synced_at: '2026-11-25T01:00:00Z',
      message: 'Synchronized 1 account(s) and 4 new transaction(s).',
    });
    vi.mocked(financeApi.listBankingSyncRuns).mockResolvedValue([
      {
        id: 'run-1',
        connection_id: 'conn-1',
        status: 'success',
        accounts_synced: 1,
        transactions_synced: 4,
        started_at: '2026-11-25T01:00:00Z',
        completed_at: '2026-11-25T01:00:01Z',
      },
    ]);

    render(<BankingPage onNavigate={onNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('Discover Accounts')).toBeInTheDocument();
    });

    // Discover & Import
    fireEvent.click(screen.getByText('Discover Accounts'));
    await waitFor(() => {
      expect(screen.getByText('DNB Salary Savings Account')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Import Selected'));
    await waitFor(() => {
      expect(financeApi.importBankingAccounts).toHaveBeenCalledWith('conn-1', ['dnb_sav_001']);
    });

    // Sync Now
    fireEvent.click(screen.getByText('Sync Now'));
    await waitFor(() => {
      expect(
        screen.getByText('Synchronized 1 account(s) and 4 new transaction(s).')
      ).toBeInTheDocument();
    });

    // Sync History modal
    fireEvent.click(screen.getByText('Sync History'));
    await waitFor(() => {
      expect(screen.getByText(/Synchronization History/i)).toBeInTheDocument();
      expect(screen.getByText(/new tx\(s\)/i)).toBeInTheDocument();
    });

    expect(alertSpy).not.toHaveBeenCalled();
    alertSpy.mockRestore();
  });
});
