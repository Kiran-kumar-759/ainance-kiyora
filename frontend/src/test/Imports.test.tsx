import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ImportsPage } from '../pages/imports/ImportsPage';
import { financeApi } from '../services/financeApi';
import { importsApi } from '../services/importsApi';
import { ImportBatch, ImportRow } from '../types/imports';

vi.mock('../services/financeApi', () => ({
  financeApi: {
    listAccounts: vi.fn(),
    listCategories: vi.fn(),
  },
}));

vi.mock('../services/importsApi', () => ({
  importsApi: {
    uploadStatement: vi.fn(),
    listImports: vi.fn(),
    listMappingProfiles: vi.fn(),
    getImport: vi.fn(),
    getPreview: vi.fn(),
    deleteImport: vi.fn(),
    getColumns: vi.fn(),
    saveMapping: vi.fn(),
    validateImport: vi.fn(),
    listRows: vi.fn(),
    bulkSelectRows: vi.fn(),
    updateRow: vi.fn(),
    listDuplicates: vi.fn(),
    reviewDuplicate: vi.fn(),
    commitImport: vi.fn(),
    getSummary: vi.fn(),
  },
}));

const sampleAccount = {
  id: 'acc-1',
  user_id: 'u-1',
  name: 'HDFC Salary',
  account_type: 'savings' as const,
  currency: 'INR',
  opening_balance: '50000.00',
  current_balance: '50000.00',
  status: 'active' as const,
  source: 'manual' as const,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
};

const makeBatch = (overrides: Partial<ImportBatch> = {}): ImportBatch => ({
  id: 'batch-1',
  user_id: 'u-1',
  account_id: 'acc-1',
  account_name: 'HDFC Salary',
  account_type: 'savings',
  original_filename: 'hdfc_nov.csv',
  file_hash: 'abc123',
  file_size: 2048,
  file_type: 'csv',
  status: 'mapping_required',
  sheet_name: 'CSV',
  header_row_index: 0,
  delimiter: ',',
  total_rows: 3,
  valid_rows: 2,
  invalid_rows: 0,
  needs_review_rows: 0,
  duplicate_rows: 0,
  potential_duplicate_rows: 1,
  imported_rows: 0,
  skipped_rows: 0,
  total_income: '0.00',
  total_expenses: '0.00',
  mapping_configuration: null,
  lifecycle_history: [],
  failure_reason: null,
  created_at: '2026-11-20T10:00:00Z',
  updated_at: '2026-11-20T10:00:00Z',
  completed_at: null,
  ...overrides,
});

describe('Frontend Bank Statement Imports Workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(financeApi.listAccounts).mockResolvedValue([sampleAccount]);
    vi.mocked(financeApi.listCategories).mockResolvedValue([
      {
        id: 'cat-1',
        name: 'Groceries',
        category_type: 'expense',
        is_system: true,
        created_at: '2026-11-01T00:00:00Z',
      },
    ]);
  });

  it('renders import center metrics, empty state, and error recovery cleanly', async () => {
    vi.mocked(importsApi.listImports).mockRejectedValueOnce(new Error('Network offline'));

    render(<ImportsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Network offline')).toBeInTheDocument();
    });

    vi.mocked(importsApi.listImports).mockResolvedValueOnce({
      total_imports: 0,
      completed_imports: 0,
      failed_imports: 0,
      transactions_imported: 0,
      batches: [],
    });

    fireEvent.click(screen.getByText('Retry'));

    await waitFor(() => {
      expect(screen.getByText('No bank statements uploaded yet')).toBeInTheDocument();
      expect(screen.getByText('+ Upload First Statement')).toBeInTheDocument();
    });
  });

  it('validates unsupported file types locally and uploads valid CSV into column mapping', async () => {
    const batch = makeBatch();
    vi.mocked(importsApi.listImports).mockResolvedValue({
      total_imports: 1,
      completed_imports: 0,
      failed_imports: 0,
      transactions_imported: 0,
      batches: [batch],
    });
    vi.mocked(importsApi.uploadStatement).mockResolvedValue({
      batch,
      available_sheets: ['CSV'],
      selected_sheet: 'CSV',
      header_row_index: 0,
      delimiter: ',',
      columns: ['Txn Date', 'Particulars', 'Debit', 'Credit'],
      preview_rows: [['01/11/2026', 'Salary', '', '85000.00']],
      sample_mapped_rows: [{ 'Txn Date': '01/11/2026', Particulars: 'Salary', Debit: '', Credit: '85000.00' }],
      suggested_mapping: {
        date_column: 'Txn Date',
        description_column: 'Particulars',
        amount_mode: 'split',
        debit_column: 'Debit',
        credit_column: 'Credit',
      },
    });
    vi.mocked(importsApi.getColumns).mockResolvedValue({
      batch_id: batch.id,
      file_type: 'csv',
      available_sheets: ['CSV'],
      selected_sheet: 'CSV',
      header_row_index: 0,
      columns: ['Txn Date', 'Particulars', 'Debit', 'Credit'],
      sample_mapped_rows: [{ 'Txn Date': '01/11/2026', Particulars: 'Salary', Debit: '', Credit: '85000.00' }],
      suggested_mapping: {
        date_column: 'Txn Date',
        description_column: 'Particulars',
        amount_mode: 'split',
        debit_column: 'Debit',
        credit_column: 'Credit',
      },
      current_mapping: null,
      saved_profiles: [],
    });

    const { container } = render(<ImportsPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('hdfc_nov.csv')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Upload Statement/i }));
    expect(screen.getByText('Upload Bank Statement')).toBeInTheDocument();

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).not.toBeNull();

    // Reject .pdf file locally
    const pdfFile = new File(['%PDF-1.4'], 'statement.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });
    expect(
      screen.getByText(/Unsupported file type\. Please choose a \.csv or \.xlsx/i)
    ).toBeInTheDocument();
    expect(importsApi.uploadStatement).not.toHaveBeenCalled();

    // Upload valid .csv file
    const csvFile = new File(['Txn Date,Particulars,Debit,Credit\n01/11/2026,Salary,,85000'], 'hdfc_nov.csv', {
      type: 'text/csv',
    });
    fireEvent.change(fileInput, { target: { files: [csvFile] } });
    fireEvent.click(screen.getByRole('button', { name: /Upload & Inspect/i }));

    await waitFor(() => {
      expect(importsApi.uploadStatement).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Map Statement Columns — hdfc_nov\.csv/i)).toBeInTheDocument();
    });
  });

  it('completes mapping -> review -> duplicate resolution -> confirmation -> commit workflow', async () => {
    const onNavigate = vi.fn();
    const mappingBatch = makeBatch({ status: 'mapping_required' });
    const reviewBatch = makeBatch({
      status: 'ready_for_review',
      total_rows: 2,
      valid_rows: 1,
      potential_duplicate_rows: 1,
    });
    const updatedReviewBatch = makeBatch({
      status: 'ready_for_review',
      total_rows: 2,
      valid_rows: 2,
      potential_duplicate_rows: 0,
    });

    const rowsInitial: ImportRow[] = [
      {
        id: 'row-1',
        import_batch_id: 'batch-1',
        source_row_number: 2,
        raw_row_data: {},
        normalized_date: '2026-11-10',
        normalized_description: 'BigBasket Order',
        normalized_merchant: 'BigBasket',
        normalized_notes: null,
        normalized_amount: '1250.00',
        normalized_type: 'expense',
        currency: 'INR',
        transaction_reference: 'UTR111',
        running_balance: null,
        row_fingerprint: 'fp1',
        validation_status: 'valid',
        duplicate_status: 'none',
        duplicate_match_transaction_id: null,
        duplicate_match_row_id: null,
        validation_errors: [],
        category_id: null,
        category_name: null,
        is_selected: true,
        review_changes: null,
        imported_transaction_id: null,
        created_at: '2026-11-20T10:00:00Z',
        updated_at: '2026-11-20T10:00:00Z',
      },
      {
        id: 'row-2',
        import_batch_id: 'batch-1',
        source_row_number: 3,
        raw_row_data: {},
        normalized_date: '2026-11-10',
        normalized_description: 'Third Wave Coffee',
        normalized_merchant: null,
        normalized_notes: null,
        normalized_amount: '220.00',
        normalized_type: 'expense',
        currency: 'INR',
        transaction_reference: null,
        running_balance: null,
        row_fingerprint: 'fp2',
        validation_status: 'potential_duplicate',
        duplicate_status: 'potential_duplicate',
        duplicate_match_transaction_id: null,
        duplicate_match_row_id: null,
        validation_errors: ['Identical date, amount, and description appears earlier in this file.'],
        category_id: null,
        category_name: null,
        is_selected: false,
        review_changes: null,
        imported_transaction_id: null,
        created_at: '2026-11-20T10:00:00Z',
        updated_at: '2026-11-20T10:00:00Z',
      },
    ];

    vi.mocked(importsApi.listImports).mockResolvedValue({
      total_imports: 1,
      completed_imports: 0,
      failed_imports: 0,
      transactions_imported: 0,
      batches: [mappingBatch],
    });
    vi.mocked(importsApi.getColumns).mockResolvedValue({
      batch_id: 'batch-1',
      file_type: 'csv',
      available_sheets: ['CSV'],
      selected_sheet: 'CSV',
      header_row_index: 0,
      columns: ['Date', 'Narration', 'Amount'],
      sample_mapped_rows: [{ Date: '10/11/2026', Narration: 'BigBasket', Amount: '-1250' }],
      suggested_mapping: {
        date_column: 'Date',
        description_column: 'Narration',
        amount_mode: 'single',
        amount_column: 'Amount',
      },
      current_mapping: null,
      saved_profiles: [],
    });
    vi.mocked(importsApi.saveMapping).mockResolvedValue(reviewBatch);
    vi.mocked(importsApi.listRows).mockResolvedValue({
      items: rowsInitial,
      total: 2,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
    vi.mocked(importsApi.getImport).mockResolvedValue(reviewBatch);
    vi.mocked(importsApi.reviewDuplicate).mockResolvedValue({
      ...rowsInitial[1],
      validation_status: 'valid',
      is_selected: true,
    });
    vi.mocked(importsApi.getSummary).mockResolvedValue({
      batch_id: 'batch-1',
      status: 'ready_for_review',
      account_id: 'acc-1',
      account_name: 'HDFC Salary',
      account_type: 'savings',
      total_rows: 2,
      valid_rows: 2,
      invalid_rows: 0,
      needs_review_rows: 0,
      duplicate_rows: 0,
      potential_duplicate_rows: 0,
      excluded_rows: 0,
      imported_rows: 0,
      selected_rows: 2,
      selected_income: '0.00',
      selected_expenses: '1470.00',
      selected_net: '-1470.00',
      imported_income: '0.00',
      imported_expenses: '0.00',
      imported_net: '0.00',
    });
    vi.mocked(importsApi.commitImport).mockResolvedValue({
      batch: { ...updatedReviewBatch, status: 'completed', imported_rows: 2 },
      summary: {
        batch_id: 'batch-1',
        status: 'completed',
        account_id: 'acc-1',
        account_name: 'HDFC Salary',
        account_type: 'savings',
        total_rows: 2,
        valid_rows: 0,
        invalid_rows: 0,
        needs_review_rows: 0,
        duplicate_rows: 0,
        potential_duplicate_rows: 0,
        excluded_rows: 0,
        imported_rows: 2,
        selected_rows: 0,
        selected_income: '0.00',
        selected_expenses: '0.00',
        selected_net: '0.00',
        imported_income: '0.00',
        imported_expenses: '1470.00',
        imported_net: '-1470.00',
      },
      imported_count: 2,
      skipped_count: 0,
      message: 'Successfully imported 2 transaction(s) into HDFC Salary.',
    });

    render(<ImportsPage onNavigate={onNavigate} />);

    // Open Map Columns
    await waitFor(() => {
      expect(screen.getByText('Map Columns')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Map Columns'));

    await waitFor(() => {
      expect(screen.getByText(/Validate & Review Transactions/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Validate & Review Transactions/i));

    // Review table loaded with potential duplicate Keep button
    await waitFor(() => {
      expect(screen.getByText('BigBasket Order')).toBeInTheDocument();
      expect(screen.getByText('Third Wave Coffee')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Keep'));
    await waitFor(() => {
      expect(importsApi.reviewDuplicate).toHaveBeenCalledWith('batch-1', 'row-2', 'import');
    });

    // Proceed to Confirm Summary
    fireEvent.click(screen.getByRole('button', { name: /Review Import Summary/i }));

    await waitFor(() => {
      expect(screen.getByText('Confirm Statement Import')).toBeInTheDocument();
      expect(screen.getByText('Confirm & Import Transactions')).toBeInTheDocument();
    });

    // Execute commit
    fireEvent.click(screen.getByRole('button', { name: /Confirm & Import Transactions/i }));

    await waitFor(() => {
      expect(screen.getByText('Import Completed')).toBeInTheDocument();
      expect(
        screen.getByText('Successfully imported 2 transaction(s) into HDFC Salary.')
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /View Imported Transactions/i }));
    expect(onNavigate).toHaveBeenCalledWith('transactions');
  });
});
