import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { IntelligencePage } from '../pages/intelligence/IntelligencePage';
import { intelligenceApi } from '../services/intelligenceApi';
import { financeApi } from '../services/financeApi';

vi.mock('../services/intelligenceApi', () => ({
  intelligenceApi: {
    getOverview: vi.fn(),
    runFullPipeline: vi.fn(),
    trainMlModel: vi.fn(),
    listCategorizations: vi.fn(),
    overrideCategorization: vi.fn(),
    listFeedback: vi.fn(),
    listMerchants: vi.fn(),
    updateMerchant: vi.fn(),
    listRecurringCandidates: vi.fn(),
    decideRecurringCandidate: vi.fn(),
    getSpendingPatterns: vi.fn(),
    listAnomalies: vi.fn(),
    reviewAnomaly: vi.fn(),
    listInsights: vi.fn(),
    reviewInsight: vi.fn(),
  },
}));

vi.mock('../services/financeApi', () => ({
  financeApi: {
    listCategories: vi.fn(),
  },
}));

describe('Phase 8 AI Expense Intelligence UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(financeApi.listCategories).mockResolvedValue([
      {
        id: 'cat-food',
        name: 'Food & Dining',
        category_type: 'expense',
        is_system: true,
        created_at: '2026-11-25T00:00:00Z',
      },
      {
        id: 'cat-groc',
        name: 'Groceries',
        category_type: 'expense',
        is_system: true,
        created_at: '2026-11-25T00:00:00Z',
      },
    ]);

    vi.mocked(intelligenceApi.getOverview).mockResolvedValue({
      metrics: {
        total_analyzed_transactions: 15,
        total_eligible_transactions: 16,
        needs_review_count: 2,
        confirmed_count: 8,
        merchant_count: 6,
        recurring_candidate_count: 2,
        pending_recurring_count: 1,
        open_anomaly_count: 1,
        high_severity_anomaly_count: 1,
        unread_insight_count: 2,
        total_insight_count: 3,
        ml_model_status: 'trained',
        ml_model_version: 'v1',
        ml_training_samples: 14,
        groq_enabled: false,
        groq_model: 'llama-3.3-70b-versatile',
        last_job_status: 'completed',
        last_job_completed_at: '2026-11-25T10:00:00Z',
      },
      model_metadata: {
        id: 'ml-1',
        model_name: 'tfidf_logreg_per_user',
        model_version: 'v1',
        status: 'trained',
        training_sample_count: 14,
        class_count: 2,
        accuracy: '0.8571',
        precision_weighted: '0.8600',
        recall_weighted: '0.8571',
        f1_weighted: '0.8550',
        confusion_matrix: { labels: ['Food & Dining', 'Transportation'], matrix: [[6, 1], [1, 6]] },
        evaluation_notes: 'Stratified holdout evaluation complete.',
        trained_at: '2026-11-25T10:00:00Z',
        updated_at: '2026-11-25T10:00:00Z',
      },
      recent_jobs: [
        {
          id: 'job-1',
          job_type: 'full_intelligence',
          status: 'completed',
          provider_name: 'local',
          model_name: 'deterministic+sklearn',
          attempt_count: 1,
          max_attempts: 3,
          items_processed: 15,
          summary: {},
          created_at: '2026-11-25T10:00:00Z',
          completed_at: '2026-11-25T10:00:02Z',
        },
      ],
      top_categories: [
        {
          category_name: 'Food & Dining',
          transaction_count: 5,
          total_amount: '4500.00',
          share_pct: '45.00',
        },
      ],
      top_anomalies: [],
      top_insights: [],
    });

    vi.mocked(intelligenceApi.listCategorizations).mockResolvedValue({
      items: [
        {
          id: 'tcat-1',
          transaction_id: 'tx-1',
          merchant_id: 'm-1',
          transaction_date: '2026-11-20',
          transaction_type: 'expense',
          amount: '420.00',
          currency: 'INR',
          description: 'UPI/SWIGGY@ICICI/1234',
          normalized_merchant_name: 'Swiggy',
          current_category_id: null,
          current_category_name: null,
          suggested_category_id: 'cat-food',
          suggested_category_name: 'Food & Dining',
          predicted_category_name: 'Food & Dining',
          classification_method: 'deterministic_rule',
          confidence: '0.9200',
          explanation: "Matched known Indian merchant 'Swiggy'.",
          evidence: {},
          review_status: 'needs_review',
          analyzed_at: '2026-11-25T10:00:00Z',
          updated_at: '2026-11-25T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      needs_review_count: 1,
      confirmed_count: 0,
    });

    vi.mocked(intelligenceApi.listFeedback).mockResolvedValue([]);
    vi.mocked(intelligenceApi.listMerchants).mockResolvedValue({
      items: [
        {
          id: 'm-1',
          canonical_key: 'swiggy',
          normalized_name: 'Swiggy',
          default_category_id: 'cat-food',
          default_category_name: 'Food & Dining',
          is_user_confirmed: false,
          transaction_count: 5,
          total_spent: '2100.00',
          aliases: [
            {
              id: 'a-1',
              raw_pattern: 'UPI/SWIGGY@ICICI/1234',
              normalized_token: 'swiggy',
              occurrence_count: 5,
              created_at: '2026-11-25T10:00:00Z',
            },
          ],
          updated_at: '2026-11-25T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });

    vi.mocked(intelligenceApi.listRecurringCandidates).mockResolvedValue({
      items: [
        {
          id: 'rc-1',
          merchant_key: 'netflix',
          merchant_name: 'Netflix',
          suggested_category_name: 'Subscriptions',
          commitment_type: 'subscription',
          frequency: 'monthly',
          estimated_amount: '499.00',
          min_amount: '499.00',
          max_amount: '499.00',
          amount_variability_pct: '0.00',
          is_variable_amount: false,
          occurrence_count: 3,
          first_seen_date: '2026-09-10',
          last_seen_date: '2026-11-10',
          next_expected_date: '2026-12-10',
          confidence: '0.9400',
          detection_method: 'interval_and_variance_v1',
          evidence: {},
          review_status: 'pending',
          updated_at: '2026-11-25T10:00:00Z',
        },
      ],
      total: 1,
      pending_count: 1,
      confirmed_count: 0,
    });

    vi.mocked(intelligenceApi.getSpendingPatterns).mockResolvedValue({
      period_start: '2026-06-01',
      period_end: '2026-11-25',
      total_expense: '15000.00',
      total_income: '85000.00',
      recurring_total: '3500.00',
      non_recurring_total: '11500.00',
      fixed_total: '4000.00',
      variable_total: '11000.00',
      essential_total: '9000.00',
      discretionary_total: '6000.00',
      weekend_expense: '4500.00',
      weekday_expense: '10500.00',
      weekend_share_pct: '30.00',
      top_merchant_concentration_pct: '25.00',
      top_3_merchant_concentration_pct: '55.00',
      by_category: [],
      by_merchant: [
        { label: 'Swiggy', amount: '2100.00', transaction_count: 5, share_pct: '14.00' },
      ],
      monthly_trend: [],
      weekly_trend: [],
      day_of_week_trend: [
        { day_name: 'Monday', day_index: 0, total_expense: '2000.00', transaction_count: 2 },
      ],
    });

    vi.mocked(intelligenceApi.listAnomalies).mockResolvedValue({
      items: [
        {
          id: 'anom-1',
          category_name: 'Food & Dining',
          merchant_name: 'Fine Dining',
          anomaly_type: 'category_transaction_spike',
          observed_amount: '5500.00',
          baseline_amount: '350.00',
          deviation_pct: '1471.43',
          severity: 'high',
          confidence: '0.9200',
          detection_method: 'robust_median_mad',
          explanation: 'Expense is significantly higher than category median.',
          supporting_transaction_ids: ['tx-9'],
          review_status: 'open',
          detected_at: '2026-11-25T10:00:00Z',
        },
      ],
      total: 1,
      open_count: 1,
      acknowledged_count: 0,
      dismissed_count: 0,
    });

    vi.mocked(intelligenceApi.listInsights).mockResolvedValue({
      items: [
        {
          id: 'ins-1',
          insight_type: 'spending_mix',
          title: 'Discretionary spending accounts for 40% of outflows',
          description: 'Verified period expense mix summary.',
          severity: 'info',
          supporting_data: {},
          calculation_method: 'essential_vs_discretionary_ratio',
          provider_name: 'local',
          confidence: '0.9200',
          suggested_action: 'Review optional dining expenses.',
          status: 'new',
          generated_at: '2026-11-25T10:00:00Z',
        },
      ],
      total: 1,
      new_count: 1,
      read_count: 0,
      dismissed_count: 0,
    });
  });

  it('renders overview and switches across all 7 intelligence tabs with interactive actions', async () => {
    const onNavigate = vi.fn();
    vi.mocked(intelligenceApi.overrideCategorization).mockResolvedValue({
      id: 'tcat-1',
      transaction_id: 'tx-1',
      transaction_date: '2026-11-20',
      transaction_type: 'expense',
      amount: '420.00',
      currency: 'INR',
      classification_method: 'user_confirmed',
      confidence: '1.0000',
      evidence: {},
      review_status: 'confirmed',
      analyzed_at: '2026-11-25T10:00:00Z',
      updated_at: '2026-11-25T10:00:00Z',
    });
    vi.mocked(intelligenceApi.reviewAnomaly).mockResolvedValue({
      id: 'anom-1',
      anomaly_type: 'category_transaction_spike',
      observed_amount: '5500.00',
      baseline_amount: '350.00',
      deviation_pct: '1471.43',
      severity: 'high',
      confidence: '0.9200',
      detection_method: 'robust_median_mad',
      explanation: 'Confirmed',
      supporting_transaction_ids: [],
      review_status: 'acknowledged',
      detected_at: '2026-11-25T10:00:00Z',
    });

    render(<IntelligencePage onNavigate={onNavigate} />);

    // Overview metrics
    await waitFor(() => {
      expect(screen.getByText('AI Expense Intelligence')).toBeInTheDocument();
      expect(screen.getByText('Per-User ML Classifier Evaluation')).toBeInTheDocument();
      expect(screen.getAllByText('85.7%').length).toBeGreaterThanOrEqual(1);
    });

    // Switch to Transaction Intelligence & confirm category
    fireEvent.click(screen.getByRole('button', { name: /Transaction Intelligence/i }));
    await waitFor(() => expect(screen.getByText('UPI/SWIGGY@ICICI/1234')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Confirm/i }));
    await waitFor(() =>
      expect(intelligenceApi.overrideCategorization).toHaveBeenCalledWith('tx-1', {
        category_id: 'cat-food',
        save_merchant_mapping: true,
        action: 'confirm',
      })
    );

    // Merchants tab
    fireEvent.click(screen.getByRole('button', { name: /Merchants/i }));
    await waitFor(() => expect(screen.getByText('Swiggy')).toBeInTheDocument());

    // Recurring tab
    fireEvent.click(screen.getByRole('button', { name: /Recurring Payments/i }));
    await waitFor(() => expect(screen.getByText('Netflix')).toBeInTheDocument());

    // Spending Patterns tab
    fireEvent.click(screen.getByRole('button', { name: /Spending Patterns/i }));
    await waitFor(() => expect(screen.getByText('Weekend Spend Share')).toBeInTheDocument());

    // Anomalies tab & acknowledge action
    fireEvent.click(screen.getByRole('button', { name: /Anomalies/i }));
    await waitFor(() =>
      expect(screen.getByText('Expense is significantly higher than category median.')).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }));
    await waitFor(() =>
      expect(intelligenceApi.reviewAnomaly).toHaveBeenCalledWith('anom-1', 'acknowledge')
    );

    // Insights tab
    fireEvent.click(screen.getByRole('button', { name: /AI Insights/i }));
    await waitFor(() =>
      expect(
        screen.getByText('Discretionary spending accounts for 40% of outflows')
      ).toBeInTheDocument()
    );
  });
});
