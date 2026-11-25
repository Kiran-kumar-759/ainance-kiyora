export type DocumentCategory =
  | 'electricity_bill'
  | 'water_bill'
  | 'gas_bill'
  | 'internet_bill'
  | 'mobile_bill'
  | 'credit_card_statement'
  | 'bank_statement'
  | 'shopping_receipt'
  | 'travel_receipt'
  | 'medical_receipt'
  | 'insurance'
  | 'tax'
  | 'loan'
  | 'subscription_invoice'
  | 'other';

export interface DocumentLinkItem {
  id: string;
  target_type: 'bill' | 'transaction' | 'subscription' | 'loan';
  link_role: string;
  bill_id?: string | null;
  transaction_id?: string | null;
  subscription_id?: string | null;
  loan_id?: string | null;
  target_label?: string | null;
  created_at: string;
}

export interface DocumentProcessingJob {
  id: string;
  document_id: string;
  document_filename?: string | null;
  job_type: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  attempt_count: number;
  max_attempts: number;
  next_retry_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  created_at: string;
}

export interface DocumentReviewEvent {
  id: string;
  action: string;
  changes: Record<string, unknown>;
  notes?: string | null;
  created_at: string;
}

export interface ExtractedLineItem {
  description: string;
  quantity?: string | number | null;
  unit_price?: string | number | null;
  total?: string | number | null;
}

export interface DocumentExtraction {
  id: string;
  document_id: string;
  ocr_engine: string;
  ocr_engine_version?: string | null;
  raw_text?: string | null;
  raw_structured_data?: Record<string, unknown> | null;

  merchant_name?: string | null;
  merchant_address?: string | null;
  merchant_phone?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  payment_date?: string | null;
  bill_period?: string | null;
  detected_document_type?: string | null;

  currency?: string | null;
  subtotal?: string | number | null;
  taxable_amount?: string | number | null;
  total_tax?: string | number | null;
  grand_total?: string | number | null;
  amount_paid?: string | number | null;
  outstanding_amount?: string | number | null;

  gstin?: string | null;
  cgst?: string | number | null;
  sgst?: string | number | null;
  igst?: string | number | null;
  tax_percentage?: string | number | null;

  line_items: ExtractedLineItem[];
  field_confidence: Record<string, number>;
  field_decisions: Record<string, 'accepted' | 'rejected' | 'edited'>;
  validation_errors: string[];
  validation_warnings: string[];
  processing_metadata: Record<string, unknown>;
  overall_confidence?: string | number | null;
  extracted_at: string;
  updated_at: string;
}

export interface FinancialDocumentSummary {
  id: string;
  original_filename: string;
  file_type: string;
  content_type: string;
  file_size: number;
  file_hash: string;
  document_category: DocumentCategory;
  source: string;
  is_duplicate_of_id?: string | null;
  duplicate_flag: boolean;
  processing_status: string;
  ocr_status: string;
  page_count?: number | null;
  rejection_reason?: string | null;
  uploaded_at: string;
  processed_at?: string | null;
  confirmed_at?: string | null;
  rejected_at?: string | null;
  links: DocumentLinkItem[];
  merchant_name?: string | null;
  grand_total?: string | number | null;
  invoice_date?: string | null;
  due_date?: string | null;
}

export interface FinancialDocumentDetail extends FinancialDocumentSummary {
  extraction?: DocumentExtraction | null;
  jobs: DocumentProcessingJob[];
  review_events: DocumentReviewEvent[];
}

export interface DocumentListResponse {
  items: FinancialDocumentSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DocumentOverview {
  total_documents: number;
  processed_count: number;
  needs_review_count: number;
  processing_count: number;
  failed_count: number;
  confirmed_count: number;
  rejected_count: number;
  recent_documents: FinancialDocumentSummary[];
}

export interface EmailConnection {
  id?: string | null;
  provider: string;
  email_address?: string | null;
  status: string;
  oauth_configured: boolean;
  scopes: string[];
  last_history_id?: string | null;
  last_sync_at?: string | null;
  last_error?: string | null;
}

export interface EmailSyncHistoryItem {
  id: string;
  connection_id: string;
  sync_mode: string;
  status: string;
  messages_scanned: number;
  relevant_messages: number;
  attachments_processed: number;
  duplicate_candidates: number;
  candidates_needing_review: number;
  failed_jobs: number;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
}

export interface EmailAttachmentSummary {
  id: string;
  filename: string;
  content_type: string;
  file_size: number;
  file_hash?: string | null;
  document_id?: string | null;
  is_supported: boolean;
  processing_status: string;
}

export interface EmailMessageSummary {
  id: string;
  provider_message_id: string;
  sender?: string | null;
  subject?: string | null;
  received_at?: string | null;
  snippet_text?: string | null;
  body_text?: string | null;
  relevance_category?: string | null;
  attachments: EmailAttachmentSummary[];
}

export interface EmailCandidate {
  id: string;
  connection_id: string;
  message_id: string;
  attachment_id?: string | null;
  document_id?: string | null;
  status: string;
  duplicate_status: string;
  duplicate_reason?: string | null;
  merchant_name?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  amount?: string | number | null;
  currency?: string | null;
  extracted_summary: Record<string, unknown>;
  created_at: string;
  reviewed_at?: string | null;
  message?: EmailMessageSummary | null;
}

export interface SmsIngestionStatus {
  enabled: boolean;
  provider: string;
  available: boolean;
  outgoing_reminders_active: boolean;
  limitation_reason: string;
  supported_platforms_note: string;
}
