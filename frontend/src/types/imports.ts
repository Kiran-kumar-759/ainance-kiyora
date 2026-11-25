export type ImportBatchStatus =
  | 'uploaded'
  | 'parsing'
  | 'mapping_required'
  | 'validating'
  | 'ready_for_review'
  | 'importing'
  | 'completed'
  | 'completed_with_errors'
  | 'failed'
  | 'cancelled';

export type ImportRowValidationStatus =
  | 'valid'
  | 'invalid'
  | 'needs_review'
  | 'duplicate'
  | 'potential_duplicate'
  | 'excluded'
  | 'imported';

export interface ImportMappingConfig {
  date_column: string;
  description_column: string;
  amount_mode: 'single' | 'split';
  amount_column?: string | null;
  debit_column?: string | null;
  credit_column?: string | null;
  type_column?: string | null;
  sign_convention: 'negative_is_expense' | 'positive_is_expense';
  reference_column?: string | null;
  balance_column?: string | null;
  merchant_column?: string | null;
  notes_column?: string | null;
  currency_column?: string | null;
  date_format: 'auto' | 'DD/MM/YYYY' | 'DD-MM-YYYY' | 'YYYY-MM-DD' | 'DD MMM YYYY' | 'MM/DD/YYYY';
  default_currency: string;
  sheet_name?: string | null;
  header_row_index?: number | null;
  delimiter?: string | null;
  save_profile_name?: string | null;
}

export interface ImportLifecycleEvent {
  from?: string | null;
  to: string;
  at: string;
  note?: string;
}

export interface ImportBatch {
  id: string;
  user_id: string;
  account_id: string;
  account_name?: string | null;
  account_type?: string | null;
  original_filename: string;
  file_hash: string;
  file_size: number;
  file_type: 'csv' | 'xlsx' | string;
  status: ImportBatchStatus;
  sheet_name?: string | null;
  header_row_index: number;
  delimiter?: string | null;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  needs_review_rows: number;
  duplicate_rows: number;
  potential_duplicate_rows: number;
  imported_rows: number;
  skipped_rows: number;
  total_income: string | number;
  total_expenses: string | number;
  mapping_configuration?: Partial<ImportMappingConfig> | null;
  lifecycle_history: ImportLifecycleEvent[];
  failure_reason?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface ImportCenterOverview {
  total_imports: number;
  completed_imports: number;
  failed_imports: number;
  transactions_imported: number;
  batches: ImportBatch[];
}

export interface ImportPreview {
  batch: ImportBatch;
  available_sheets: string[];
  selected_sheet: string;
  header_row_index: number;
  delimiter?: string | null;
  columns: string[];
  preview_rows: string[][];
  sample_mapped_rows: Record<string, unknown>[];
  suggested_mapping: Partial<ImportMappingConfig>;
}

export interface ImportMappingProfile {
  id: string;
  profile_name: string;
  file_format: string;
  mapping_configuration: Partial<ImportMappingConfig>;
  created_at: string;
}

export interface ImportColumns {
  batch_id: string;
  file_type: string;
  available_sheets: string[];
  selected_sheet: string;
  header_row_index: number;
  columns: string[];
  sample_mapped_rows: Record<string, unknown>[];
  suggested_mapping: Partial<ImportMappingConfig>;
  current_mapping?: Partial<ImportMappingConfig> | null;
  saved_profiles: ImportMappingProfile[];
}

export interface ImportRow {
  id: string;
  import_batch_id: string;
  source_row_number: number;
  raw_row_data: Record<string, unknown>;
  normalized_date?: string | null;
  normalized_description?: string | null;
  normalized_merchant?: string | null;
  normalized_notes?: string | null;
  normalized_amount?: string | number | null;
  normalized_type?: 'income' | 'expense' | null;
  currency: string;
  transaction_reference?: string | null;
  running_balance?: string | number | null;
  row_fingerprint?: string | null;
  validation_status: ImportRowValidationStatus;
  duplicate_status: string;
  duplicate_match_transaction_id?: string | null;
  duplicate_match_row_id?: string | null;
  validation_errors: string[];
  category_id?: string | null;
  category_name?: string | null;
  is_selected: boolean;
  review_changes?: Record<string, unknown> | null;
  imported_transaction_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImportRowListResponse {
  items: ImportRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ImportSummary {
  batch_id: string;
  status: ImportBatchStatus;
  account_id: string;
  account_name: string;
  account_type: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  needs_review_rows: number;
  duplicate_rows: number;
  potential_duplicate_rows: number;
  excluded_rows: number;
  imported_rows: number;
  selected_rows: number;
  selected_income: string | number;
  selected_expenses: string | number;
  selected_net: string | number;
  imported_income: string | number;
  imported_expenses: string | number;
  imported_net: string | number;
}

export interface ImportCommitResponse {
  batch: ImportBatch;
  summary: ImportSummary;
  imported_count: number;
  skipped_count: number;
  message: string;
}
