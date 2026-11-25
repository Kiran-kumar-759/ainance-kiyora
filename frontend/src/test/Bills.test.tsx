import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BillsPage } from '../pages/bills/BillsPage';
import { billsApi } from '../services/billsApi';
import { financeApi } from '../services/financeApi';
import { Bill, BillsOverview } from '../types/bills';

vi.mock('../services/billsApi', () => ({
  billsApi: {
    getOverview: vi.fn(),
    listBills: vi.fn(),
    getBill: vi.fn(),
    createBill: vi.fn(),
    updateBill: vi.fn(),
    archiveBill: vi.fn(),
    recordPayment: vi.fn(),
    linkTransaction: vi.fn(),
    listPayments: vi.fn(),
    listSchedules: vi.fn(),
    updateSchedule: vi.fn(),
    generateNextOccurrence: vi.fn(),
    updateReminders: vi.fn(),
    processReminders: vi.fn(),
    uploadDocument: vi.fn(),
    downloadDocument: vi.fn(),
    listNotifications: vi.fn(),
    getUnreadCount: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  },
}));

vi.mock('../services/financeApi', () => ({
  financeApi: {
    listAccounts: vi.fn(),
    listCategories: vi.fn(),
    listTransactions: vi.fn(),
  },
}));

const sampleBill: Bill = {
  id: 'bill-1',
  user_id: 'user-1',
  parent_schedule_id: 'sched-1',
  financial_category_id: 'cat-1',
  financial_category_name: 'Utilities & Bills',
  linked_account_id: null,
  linked_account_name: null,
  bill_name: 'BESCOM Electricity',
  bill_category: 'electricity',
  provider_name: 'BESCOM',
  account_reference: 'CA-102938',
  description: 'Monthly home power bill',
  bill_type: 'recurring',
  frequency: 'monthly',
  is_variable_amount: false,
  expected_amount: '2450.00',
  current_amount: '2450.00',
  amount_paid_total: '0.00',
  remaining_due: '2450.00',
  is_amount_unknown: false,
  currency: 'INR',
  billing_period_start: '2026-11-01',
  billing_period_end: '2026-11-30',
  due_date: '2026-11-28',
  paid_at: null,
  stored_status: 'unpaid',
  derived_status: 'due_soon',
  days_until_due: 3,
  preferred_payment_method: 'upi',
  reminder_enabled: true,
  reminder_days_before: [7, 3, 1, 0],
  notification_channels: { in_app: true, email: false, sms: false },
  is_active: true,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-01T10:00:00Z',
  payments: [],
  reminders: [
    {
      id: 'rem-1',
      bill_id: 'bill-1',
      offset_days: 3,
      reminder_at: '2026-11-25T03:30:00Z',
      channels: ['in_app'],
      is_enabled: true,
      delivery_status: 'pending',
      channel_outcomes: {},
      retry_count: 0,
      max_retries: 3,
      next_retry_at: null,
      last_attempt_at: null,
      delivered_at: null,
      idempotency_key: 'bill-1:3:2026-11-28',
    },
  ],
  documents: [],
  schedule: null,
};

const unknownVariableBill: Bill = {
  ...sampleBill,
  id: 'bill-2',
  bill_name: 'Indane Gas Cylinder',
  bill_category: 'gas',
  provider_name: 'Indane',
  bill_type: 'one_time',
  frequency: null,
  is_variable_amount: true,
  expected_amount: null,
  current_amount: null,
  remaining_due: null,
  is_amount_unknown: true,
  derived_status: 'upcoming',
  days_until_due: 10,
};

const sampleOverview: BillsOverview = {
  upcoming_count: 1,
  due_soon_count: 1,
  overdue_count: 0,
  paid_count: 1,
  total_upcoming_known_amount: '2450.00',
  total_overdue_known_amount: '0.00',
  total_paid_amount: '1200.00',
  unknown_variable_bills_count: 1,
  next_payment_due: sampleBill,
  recent_payments: [],
  unread_notifications_count: 1,
  due_soon_threshold_days: 5,
};

describe('Phase 5 Bills, Payments & Reminders Frontend', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(billsApi.getOverview).mockResolvedValue(sampleOverview);
    vi.mocked(billsApi.listBills).mockResolvedValue({
      items: [sampleBill, unknownVariableBill],
      total: 2,
      page: 1,
      page_size: 15,
      total_pages: 1,
    });
    vi.mocked(billsApi.listPayments).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(billsApi.listSchedules).mockResolvedValue([
      {
        id: 'sched-1',
        bill_name: 'BESCOM Electricity',
        bill_category: 'electricity',
        provider_name: 'BESCOM',
        frequency: 'monthly',
        custom_interval_days: null,
        anchor_day: 28,
        is_variable_amount: false,
        expected_amount: '2450.00',
        currency: 'INR',
        start_date: '2026-11-28',
        end_date: null,
        next_due_date: '2026-12-28',
        is_active: true,
      },
    ]);
    vi.mocked(billsApi.listNotifications).mockResolvedValue({
      items: [
        {
          id: 'notif-1',
          user_id: 'user-1',
          title: 'Bill Due Soon: BESCOM Electricity',
          message: '₹2,450.00 due in 3 day(s)',
          notification_type: 'bill_due_soon',
          related_bill_id: 'bill-1',
          related_payment_id: null,
          is_read: false,
          read_at: null,
          created_at: '2026-11-25T09:00:00Z',
        },
      ],
      total: 1,
      unread_count: 1,
    });
    vi.mocked(financeApi.listAccounts).mockResolvedValue([
      {
        id: 'acc-1',
        user_id: 'user-1',
        name: 'HDFC Savings',
        account_type: 'savings',
        institution_name: 'HDFC',
        account_identifier: '1234',
        currency: 'INR',
        opening_balance: '50000.00',
        current_balance: '50000.00',
        status: 'active',
        source: 'manual',
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
    ]);
    vi.mocked(financeApi.listCategories).mockResolvedValue([]);
    vi.mocked(financeApi.listTransactions).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
  });

  it('renders bills overview cards, variable unknown-amount notice, and bill rows cleanly', async () => {
    render(<BillsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText('BESCOM Electricity').length).toBeGreaterThan(0);
    });

    expect(screen.getByText('Bills, Payments & Reminders')).toBeInTheDocument();
    expect(screen.getByText(/variable-amount bill\(s\) await actual billed amount/i)).toBeInTheDocument();
    expect(screen.getByText('Indane Gas Cylinder')).toBeInTheDocument();
    expect(screen.getByText('Variable (Pending)')).toBeInTheDocument();
  });

  it('handles error recovery gracefully when bills API fails', async () => {
    vi.mocked(billsApi.getOverview).mockRejectedValueOnce(new Error('Database timeout'));
    render(<BillsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Database timeout')).toBeInTheDocument();
    });
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('supports creating a recurring or one-time bill with conditional frequency field', async () => {
    vi.mocked(billsApi.createBill).mockResolvedValue(sampleBill);
    render(<BillsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Add Bill')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Add Bill'));

    // Frequency visible by default for recurring
    expect(screen.getByLabelText('Recurrence Frequency')).toBeInTheDocument();

    // Switch to One-Time hides frequency
    fireEvent.change(screen.getByLabelText('Bill Type'), { target: { value: 'one_time' } });
    expect(screen.queryByLabelText('Recurrence Frequency')).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/BESCOM Electricity, Airtel Fiber/i), {
      target: { value: 'Municipal Property Tax' },
    });
    // Simulate keystroke-by-keystroke typing (6 -> 60 -> 600) to confirm expected_amount stays synced
    const amtInput = screen.getByPlaceholderText('0.00');
    fireEvent.change(amtInput, { target: { value: '6' } });
    fireEvent.change(amtInput, { target: { value: '60' } });
    fireEvent.change(amtInput, { target: { value: '600' } });

    fireEvent.click(screen.getByText('Create Bill'));

    await waitFor(() => {
      expect(billsApi.createBill).toHaveBeenCalledWith(
        expect.objectContaining({
          bill_name: 'Municipal Property Tax',
          bill_type: 'one_time',
          current_amount: '600',
          expected_amount: '600',
        })
      );
    });
  });

  it('enforces honest 2-step manual payment recording confirmation', async () => {
    vi.mocked(billsApi.recordPayment).mockResolvedValue({
      ...sampleBill,
      derived_status: 'paid',
      stored_status: 'paid',
    });

    render(<BillsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText('Record Payment').length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByText('Record Payment')[0]);

    expect(screen.getByText(/Manual Payment Recording Only:/i)).toBeInTheDocument();
    expect(screen.getByText(/execute live UPI/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Review Payment Confirmation'));
    expect(screen.getByText('Confirm & Record Payment')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Confirm & Record Payment'));

    await waitFor(() => {
      expect(billsApi.recordPayment).toHaveBeenCalledWith(
        'bill-1',
        expect.objectContaining({
          financial_account_id: 'acc-1',
          mark_as_fully_paid: true,
        })
      );
    });
  });

  it('runs due reminders honestly and manages recurring schedules and notifications tabs', async () => {
    vi.mocked(billsApi.processReminders).mockResolvedValue({
      processed_count: 1,
      delivered_count: 1,
      partial_count: 0,
      unavailable_count: 0,
      failed_count: 0,
      notifications_created: 1,
      email_configured: false,
      sms_configured: false,
    });
    vi.mocked(billsApi.generateNextOccurrence).mockResolvedValue({
      created: true,
      message: 'Next recurring bill occurrence generated.',
      occurrence: sampleBill,
    });
    vi.mocked(billsApi.markNotificationRead).mockResolvedValue({ id: 'notif-1', is_read: true });

    render(<BillsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Run Due Reminders')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Run Due Reminders'));
    await waitFor(() => {
      expect(screen.getAllByText(/Not Configured/i).length).toBeGreaterThanOrEqual(2);
    });

    // Switch to Recurring Schedules tab
    fireEvent.click(screen.getByText(/Recurring Schedules/i));
    fireEvent.click(screen.getByText('Generate Next'));
    await waitFor(() => {
      expect(billsApi.generateNextOccurrence).toHaveBeenCalledWith('sched-1');
    });

    // Switch to Notifications tab & mark read
    fireEvent.click(screen.getByText(/Notifications \(1\)/i));
    expect(screen.getByText('Bill Due Soon: BESCOM Electricity')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Mark Read'));
    await waitFor(() => {
      expect(billsApi.markNotificationRead).toHaveBeenCalledWith('notif-1');
    });
  });
});
