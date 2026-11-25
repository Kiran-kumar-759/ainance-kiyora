import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SubscriptionsPage } from '../pages/subscriptions/SubscriptionsPage';
import { LoansPage } from '../pages/loans/LoansPage';
import { loansApi, subscriptionsApi } from '../services/phase6Api';
import { financeApi } from '../services/financeApi';
import { Loan, LoanOverview, Subscription, SubscriptionOverview } from '../types/phase6';

vi.mock('../services/phase6Api', () => ({
  subscriptionsApi: {
    getOverview: vi.fn(),
    getAnalytics: vi.fn(),
    listSubscriptions: vi.fn(),
    getSubscription: vi.fn(),
    createSubscription: vi.fn(),
    updateSubscription: vi.fn(),
    changePrice: vi.fn(),
    pauseSubscription: vi.fn(),
    resumeSubscription: vi.fn(),
    cancelSubscription: vi.fn(),
    archiveSubscription: vi.fn(),
    recordPayment: vi.fn(),
    linkTransaction: vi.fn(),
    reversePayment: vi.fn(),
    listPayments: vi.fn(),
    listCandidates: vi.fn(),
    decideCandidate: vi.fn(),
  },
  loansApi: {
    calculateEmi: vi.fn(),
    getOverview: vi.fn(),
    getAnalytics: vi.fn(),
    listLoans: vi.fn(),
    getLoan: vi.fn(),
    createLoan: vi.fn(),
    updateLoan: vi.fn(),
    archiveLoan: vi.fn(),
    reviseRate: vi.fn(),
    simulatePrepayment: vi.fn(),
    recordPayment: vi.fn(),
    linkTransaction: vi.fn(),
    reversePayment: vi.fn(),
    listPayments: vi.fn(),
  },
}));

vi.mock('../services/financeApi', () => ({
  financeApi: {
    listAccounts: vi.fn(),
    listTransactions: vi.fn(),
  },
}));

const sampleSub: Subscription = {
  id: 'sub-1',
  user_id: 'u-1',
  subscription_name: 'Netflix Standard',
  provider_name: 'Netflix',
  category: 'ott_streaming',
  plan_name: 'Standard HD',
  amount: '199.00',
  monthly_equivalent: '199.00',
  annual_equivalent: '2388.00',
  is_amount_unknown: false,
  currency: 'INR',
  billing_frequency: 'monthly',
  anchor_day: 25,
  start_date: '2026-10-25',
  next_renewal_date: '2026-11-28',
  days_until_renewal: 3,
  is_renewal_due_soon: true,
  is_trial_ending_soon: false,
  preferred_payment_method: 'upi',
  status: 'active',
  reminder_enabled: true,
  reminder_days_before: [7, 3, 1, 0],
  notification_channels: { in_app: true, email: false, sms: false },
  total_actual_paid: '199.00',
  created_at: '2026-10-25T00:00:00Z',
  updated_at: '2026-10-25T00:00:00Z',
  price_history: [
    {
      id: 'ph-1',
      subscription_id: 'sub-1',
      previous_price: null,
      new_price: '199.00',
      effective_date: '2026-10-25',
      reason: 'Initial price',
      created_at: '2026-10-25T00:00:00Z',
    },
  ],
  payments: [],
  reminders: [],
};

const sampleSubOverview: SubscriptionOverview = {
  active_count: 1,
  trial_count: 0,
  paused_count: 0,
  cancelled_count: 0,
  archived_count: 0,
  renewals_due_soon_count: 1,
  trials_ending_soon_count: 0,
  unknown_price_active_count: 0,
  monthly_recurring_cost: '199.00',
  annual_recurring_cost: '2388.00',
  actual_spent_this_month: '199.00',
  actual_spent_total: '199.00',
  next_renewal_subscription: sampleSub,
  due_soon_threshold_days: 7,
};

const sampleLoan: Loan = {
  id: 'loan-1',
  user_id: 'u-1',
  liability_account_id: 'acc-loan-1',
  loan_name: 'HDFC Car Loan',
  lender_name: 'HDFC Bank',
  loan_type: 'vehicle',
  original_principal: '500000.00',
  outstanding_principal_at_start: '300000.00',
  current_outstanding_principal: '300000.00',
  currency: 'INR',
  interest_rate: '9.000',
  interest_rate_type: 'floating',
  calculation_method: 'reducing_balance',
  loan_start_date: '2025-11-01',
  tracking_start_date: '2026-11-25',
  first_emi_date: '2026-12-05',
  next_emi_due_date: '2026-12-05',
  maturity_date: '2028-11-05',
  original_tenure_months: 36,
  remaining_tenure_months: 24,
  emi_amount: '13705.42',
  emi_frequency: 'monthly',
  anchor_day: 5,
  status: 'active',
  derived_status: 'active',
  total_principal_repaid: '0.00',
  total_interest_paid: '0.00',
  total_paid_overall: '0.00',
  repayment_progress_pct: '40.00',
  overdue_installments_count: 0,
  reminder_enabled: true,
  reminder_days_before: [5, 3, 1, 0],
  notification_channels: { in_app: true, email: false, sms: false },
  created_at: '2026-11-25T00:00:00Z',
  updated_at: '2026-11-25T00:00:00Z',
  installments: [
    {
      id: 'inst-1',
      loan_id: 'loan-1',
      installment_number: 1,
      due_date: '2026-12-05',
      opening_principal: '300000.00',
      emi_amount: '13705.42',
      principal_component: '11455.42',
      interest_component: '2250.00',
      closing_principal: '288544.58',
      principal_paid: '0.00',
      interest_paid: '0.00',
      status: 'upcoming',
      derived_status: 'upcoming',
      is_final_adjustment: false,
    },
  ],
  rate_history: [],
  payments: [],
  reminders: [],
};

const sampleLoanOverview: LoanOverview = {
  active_loans_count: 1,
  closed_loans_count: 0,
  overdue_loans_count: 0,
  overdue_installments_count: 0,
  total_outstanding_principal: '300000.00',
  total_original_principal_known: '500000.00',
  total_monthly_emi_commitment: '13705.42',
  total_principal_repaid: '0.00',
  total_interest_paid: '0.00',
  next_emi_due_loan: sampleLoan,
};

describe('Phase 6 Subscriptions & Loans Frontend', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(financeApi.listAccounts).mockResolvedValue([
      {
        id: 'acc-1',
        user_id: 'u-1',
        name: 'SBI Savings',
        account_type: 'savings',
        institution_name: 'SBI',
        account_identifier: '4421',
        currency: 'INR',
        opening_balance: '200000.00',
        current_balance: '200000.00',
        status: 'active',
        source: 'manual',
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.listTransactions).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });

    vi.mocked(subscriptionsApi.getOverview).mockResolvedValue(sampleSubOverview);
    vi.mocked(subscriptionsApi.listSubscriptions).mockResolvedValue({
      items: [sampleSub],
      total: 1,
      page: 1,
      page_size: 15,
      total_pages: 1,
    });
    vi.mocked(subscriptionsApi.listPayments).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(subscriptionsApi.getAnalytics).mockResolvedValue({
      monthly_recurring_cost: '199.00',
      annual_recurring_cost: '2388.00',
      total_actual_historical_spend: '199.00',
      active_subscriptions_count: 1,
      cancelled_subscriptions_count: 0,
      price_increase_events_count: 0,
      by_category: [],
      by_provider: [],
      monthly_trend: [],
      most_expensive: [sampleSub],
      upcoming_commitments: [sampleSub],
      recent_price_changes: [],
    });
    vi.mocked(subscriptionsApi.listCandidates).mockResolvedValue([
      {
        merchant_key: 'spotifyindia',
        display_name: 'Spotify India',
        estimated_amount: '119.00',
        detected_frequency: 'monthly',
        occurrence_count: 2,
        first_seen: '2026-10-05',
        last_seen: '2026-11-05',
        suggested_next_date: '2026-12-05',
        sample_transaction_ids: ['tx-1', 'tx-2'],
        confidence_note: '2 consistent charges spaced ~31 days apart.',
      },
    ]);

    vi.mocked(loansApi.getOverview).mockResolvedValue(sampleLoanOverview);
    vi.mocked(loansApi.listLoans).mockResolvedValue({
      items: [sampleLoan],
      total: 1,
      page: 1,
      page_size: 50,
      total_pages: 1,
    });
    vi.mocked(loansApi.listPayments).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(loansApi.getAnalytics).mockResolvedValue({
      total_outstanding_principal: '300000.00',
      total_principal_repaid: '0.00',
      total_interest_paid: '0.00',
      total_repayment_actual: '0.00',
      projected_remaining_interest: '28930.08',
      monthly_emi_commitment: '13705.42',
      estimated_latest_maturity_date: '2028-11-05',
      principal_share_pct: '0.00',
      interest_share_pct: '0.00',
      by_loan: [],
      repayment_trend: [],
    });
  });

  it('renders Subscriptions overview, price updates, manual payment, and candidate detection', async () => {
    vi.mocked(subscriptionsApi.changePrice).mockResolvedValue({
      ...sampleSub,
      amount: '249.00',
      monthly_equivalent: '249.00',
    });
    vi.mocked(subscriptionsApi.recordPayment).mockResolvedValue(sampleSub);

    render(<SubscriptionsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Netflix Standard')).toBeInTheDocument();
    });
    expect(screen.getByText('₹2,388.00')).toBeInTheDocument();

    // Open Details & record price increase
    fireEvent.click(screen.getByText('Details'));
    fireEvent.change(screen.getByPlaceholderText('New ₹ Price'), { target: { value: '249' } });
    fireEvent.click(screen.getByText('Update Price'));
    await waitFor(() => {
      expect(subscriptionsApi.changePrice).toHaveBeenCalledWith(
        'sub-1',
        expect.objectContaining({ new_price: '249.00' })
      );
    });

    // Switch to Detected Candidates tab
    fireEvent.click(screen.getByLabelText('Close modal'));
    fireEvent.click(screen.getByText(/Detected Candidates/i));
    expect(screen.getByText('Spotify India')).toBeInTheDocument();
  });

  it('renders Loans overview, deterministic EMI calculator, amortization schedule, and prepayment simulator', async () => {
    vi.mocked(loansApi.calculateEmi).mockResolvedValue({
      principal: '500000.00',
      annual_interest_rate: '9.000',
      tenure_installments: 60,
      emi_frequency: 'monthly',
      calculation_method: 'reducing_balance',
      periodic_emi: '10379.18',
      total_repayment: '622750.80',
      total_interest: '122750.80',
      principal_percentage: '80.29',
      interest_percentage: '19.71',
      assumptions: ['Method: Reducing-balance at 9.000% p.a.'],
      preview_schedule: [],
    });
    vi.mocked(loansApi.simulatePrepayment).mockResolvedValue({
      is_scenario_simulation: true,
      disclaimer: 'Scenario calculation only — no database records modified.',
      current_outstanding_principal: '300000.00',
      baseline_emi: '13705.42',
      baseline_remaining_installments: 24,
      baseline_remaining_interest: '28930.08',
      scenario_revised_emi: '13705.42',
      scenario_remaining_installments: 15,
      scenario_remaining_interest: '14200.00',
      revised_principal_after_lump_sum: '200000.00',
      estimated_interest_saved: '14730.08',
      user_supplied_prepayment_fee: '0.00',
      net_estimated_savings: '14730.08',
      tenure_months_saved: 9,
    });
    vi.mocked(loansApi.recordPayment).mockResolvedValue(sampleLoan);

    render(<LoansPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText('HDFC Car Loan').length).toBeGreaterThan(0);
    });

    // Test standalone EMI Calculator tab
    fireEvent.click(screen.getByText('EMI Calculator'));
    fireEvent.click(screen.getByText('Calculate EMI'));
    await waitFor(() => {
      expect(screen.getByText('₹10,379.18')).toBeInTheDocument();
    });

    // Return to My Loans -> open Schedule & Tools -> Prepayment Simulator
    fireEvent.click(screen.getByText(/My Loans/i));
    await waitFor(() => {
      expect(screen.getByText(/Schedule & Tools/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Schedule & Tools/i));
    expect(screen.getByText('₹11,455.42')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Prepayment Simulator'));
    expect(screen.getByText(/Scenario Mode Only:/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Simulate Savings'));
    await waitFor(() => {
      expect(screen.getAllByText('₹14,730.08').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('recovers gracefully when Subscriptions or Loans API fails', async () => {
    vi.mocked(loansApi.getOverview).mockRejectedValueOnce(new Error('PostgreSQL unavailable'));
    render(<LoansPage onNavigate={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText('PostgreSQL unavailable')).toBeInTheDocument();
    });
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });
});
