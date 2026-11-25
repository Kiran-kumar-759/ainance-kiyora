import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DocumentsPage } from '../pages/documents/DocumentsPage';
import { documentsApi, emailIngestionApi } from '../services/documentsApi';
import { financeApi } from '../services/financeApi';
import { billsApi } from '../services/billsApi';
import { loansApi, subscriptionsApi } from '../services/phase6Api';
import { FinancialDocumentDetail, FinancialDocumentSummary } from '../types/documents';

vi.mock('../services/documentsApi', () => ({
  documentsApi: {
    getOverview: vi.fn(),
    listDocuments: vi.fn(),
    getDocument: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    processDocument: vi.fn(),
    listProcessingHistory: vi.fn(),
    updateExtraction: vi.fn(),
    confirmDocument: vi.fn(),
    rejectDocument: vi.fn(),
    linkDocument: vi.fn(),
    fetchPreviewBlob: vi.fn(),
    fetchDownloadBlob: vi.fn(),
  },
  emailIngestionApi: {
    getConnections: vi.fn(),
    getGmailConnectUrl: vi.fn(),
    disconnectGmail: vi.fn(),
    syncGmail: vi.fn(),
    listSyncHistory: vi.fn(),
    listCandidates: vi.fn(),
    confirmCandidate: vi.fn(),
    rejectCandidate: vi.fn(),
    getSmsStatus: vi.fn(),
  },
}));

vi.mock('../services/financeApi', () => ({
  financeApi: {
    listAccounts: vi.fn(),
    listTransactions: vi.fn(),
  },
}));

vi.mock('../services/billsApi', () => ({
  billsApi: {
    listBills: vi.fn(),
  },
}));

vi.mock('../services/phase6Api', () => ({
  subscriptionsApi: {
    listSubscriptions: vi.fn(),
  },
  loansApi: {
    listLoans: vi.fn(),
  },
}));

const sampleDocSummary: FinancialDocumentSummary = {
  id: 'doc-1',
  original_filename: 'bescom_nov_2026.pdf',
  file_type: 'pdf',
  content_type: 'application/pdf',
  file_size: 42000,
  file_hash: 'abc123',
  document_category: 'electricity_bill',
  source: 'manual_upload',
  duplicate_flag: false,
  processing_status: 'needs_review',
  ocr_status: 'completed',
  page_count: 1,
  uploaded_at: '2026-11-25T10:00:00Z',
  links: [],
  merchant_name: 'BESCOM',
  grand_total: '1180.00',
  invoice_date: '2026-11-15',
  due_date: '2026-11-30',
};

const sampleDocDetail: FinancialDocumentDetail = {
  ...sampleDocSummary,
  extraction: {
    id: 'ext-1',
    document_id: 'doc-1',
    ocr_engine: 'pymupdf_text',
    raw_text: 'BESCOM\nGSTIN: 29ABCDE1234F1Z5\nGrand Total: ₹1,180.00',
    merchant_name: 'BESCOM',
    invoice_number: 'INV-2026-88',
    invoice_date: '2026-11-15',
    due_date: '2026-11-30',
    currency: 'INR',
    subtotal: '1000.00',
    total_tax: '180.00',
    grand_total: '1180.00',
    gstin: '29ABCDE1234F1Z5',
    cgst: '90.00',
    sgst: '90.00',
    line_items: [{ description: 'Electricity Usage', quantity: '1', total: '1000.00' }],
    field_confidence: { merchant_name: 0.94, grand_total: 0.96 },
    field_decisions: {},
    validation_errors: [],
    validation_warnings: [],
    processing_metadata: {},
    overall_confidence: '0.9500',
    extracted_at: '2026-11-25T10:00:05Z',
    updated_at: '2026-11-25T10:00:05Z',
  },
  jobs: [
    {
      id: 'job-1',
      document_id: 'doc-1',
      document_filename: 'bescom_nov_2026.pdf',
      job_type: 'ocr_extract',
      status: 'failed',
      attempt_count: 3,
      max_attempts: 3,
      error_message: 'Sample retry test error',
      created_at: '2026-11-25T10:00:00Z',
    },
  ],
  review_events: [],
};

describe('Phase 7 Documents, OCR Review, Email & SMS Ingestion Frontend', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(documentsApi.getOverview).mockResolvedValue({
      total_documents: 1,
      processed_count: 1,
      needs_review_count: 1,
      processing_count: 0,
      failed_count: 0,
      confirmed_count: 0,
      rejected_count: 0,
      recent_documents: [sampleDocSummary],
    });
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [sampleDocSummary],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    vi.mocked(documentsApi.getDocument).mockResolvedValue(sampleDocDetail);
    vi.mocked(documentsApi.updateExtraction).mockResolvedValue(sampleDocDetail);
    vi.mocked(documentsApi.confirmDocument).mockResolvedValue({
      ...sampleDocDetail,
      processing_status: 'confirmed',
    });
    vi.mocked(documentsApi.listProcessingHistory).mockResolvedValue({
      items: sampleDocDetail.jobs,
      total: 1,
    });
    vi.mocked(documentsApi.fetchPreviewBlob).mockResolvedValue({
      blob: new Blob(['png'], { type: 'image/png' }),
      totalPages: 1,
    });

    vi.mocked(emailIngestionApi.getConnections).mockResolvedValue([
      {
        provider: 'gmail',
        status: 'connected',
        email_address: 'kiran@gmail.com',
        oauth_configured: true,
        scopes: ['https://www.googleapis.com/auth/gmail.readonly'],
      },
    ]);
    vi.mocked(emailIngestionApi.listSyncHistory).mockResolvedValue([]);
    vi.mocked(emailIngestionApi.listCandidates).mockResolvedValue([
      {
        id: 'cand-1',
        connection_id: 'conn-1',
        message_id: 'msg-1',
        document_id: 'doc-1',
        status: 'duplicate_warning',
        duplicate_status: 'uncertain_duplicate',
        duplicate_reason: 'Similar recurring invoice detected.',
        merchant_name: 'Airtel Fiber',
        invoice_number: 'AIR-901',
        amount: '999.00',
        currency: 'INR',
        extracted_summary: {},
        created_at: '2026-11-25T10:00:00Z',
        message: {
          id: 'msg-1',
          provider_message_id: 'gm-1',
          sender: 'ebill@airtel.in',
          subject: 'Airtel Bill',
          attachments: [],
        },
      },
    ]);
    vi.mocked(emailIngestionApi.getSmsStatus).mockResolvedValue({
      enabled: false,
      provider: 'none',
      available: false,
      outgoing_reminders_active: true,
      limitation_reason: 'Incoming SMS ingestion is unavailable in web browsers.',
      supported_platforms_note: 'Requires explicit-consent Android bridge.',
    });

    vi.mocked(financeApi.listAccounts).mockResolvedValue([]);
    vi.mocked(financeApi.listTransactions).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 30,
      total_pages: 1,
    });
    vi.mocked(billsApi.listBills).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      total_pages: 1,
    });
    vi.mocked(subscriptionsApi.listSubscriptions).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      total_pages: 1,
    });
    vi.mocked(loansApi.listLoans).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      total_pages: 1,
    });
  });

  it('renders Documents overview, opens Two-Panel OCR Review, edits fields, and confirms bill creation', async () => {
    render(<DocumentsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('bescom_nov_2026.pdf')).toBeInTheDocument();
    });

    // Open Needs Review tab & Two-Panel OCR Review modal
    fireEvent.click(screen.getByText(/Needs Review \(/i));
    await waitFor(() => {
      expect(screen.getByText('Review & Extract')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Review & Extract'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Merchant Name')).toHaveValue('BESCOM');
    });

    // Edit merchant and choose Create New Unpaid Bill -> Confirm Document
    fireEvent.change(screen.getByPlaceholderText('Merchant Name'), {
      target: { value: 'BESCOM Bengaluru' },
    });
    fireEvent.change(screen.getByLabelText('Confirmation Action'), {
      target: { value: 'create_bill' },
    });
    fireEvent.click(screen.getByText('Confirm Document'));

    await waitFor(() => {
      expect(documentsApi.updateExtraction).toHaveBeenCalled();
      expect(documentsApi.confirmDocument).toHaveBeenCalledWith(
        'doc-1',
        expect.objectContaining({ action: 'create_bill', bill_name: 'BESCOM Bengaluru' })
      );
    });
  });

  it('supports Gmail sync, candidate confirmation, SMS unavailable boundary, and failed OCR retry', async () => {
    vi.mocked(emailIngestionApi.syncGmail).mockResolvedValue({
      id: 'sync-1',
      connection_id: 'conn-1',
      sync_mode: 'incremental_history',
      status: 'completed',
      messages_scanned: 3,
      relevant_messages: 1,
      attachments_processed: 1,
      duplicate_candidates: 1,
      candidates_needing_review: 1,
      failed_jobs: 0,
      started_at: '2026-11-25T10:15:00Z',
    });
    vi.mocked(emailIngestionApi.confirmCandidate).mockResolvedValue({
      id: 'cand-1',
      connection_id: 'conn-1',
      message_id: 'msg-1',
      status: 'confirmed',
      duplicate_status: 'uncertain_duplicate',
      extracted_summary: {},
      created_at: '2026-11-25T10:00:00Z',
    });
    vi.mocked(documentsApi.processDocument).mockResolvedValue(sampleDocDetail.jobs[0]);

    render(<DocumentsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/Email Imports/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Email Imports/i));

    expect(screen.getByText('Airtel Fiber')).toBeInTheDocument();
    expect(screen.getByText(/Incoming SMS Extraction Boundary/i)).toBeInTheDocument();
    expect(screen.getByText(/Unavailable \(Web SaaS\)/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Sync Now'));
    await waitFor(() => {
      expect(emailIngestionApi.syncGmail).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByText('Confirm'));
    await waitFor(() => {
      expect(emailIngestionApi.confirmCandidate).toHaveBeenCalledWith('cand-1', {
        action: 'standalone',
      });
    });

    // Check Processing History -> Retry OCR button
    fireEvent.click(screen.getByText(/Processing History/i));
    fireEvent.click(screen.getByText('Retry OCR'));
    await waitFor(() => {
      expect(documentsApi.processDocument).toHaveBeenCalledWith('doc-1');
    });
  });
});
