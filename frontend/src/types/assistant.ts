export type WebProviderId = 'langsearch' | 'firecrawl' | 'tavily';

export type EvidenceOrigin =
  | 'personal_financial_record'
  | 'personal_document'
  | 'deterministic_calculation'
  | 'forecast_or_scenario'
  | 'external_web'
  | 'general_explanation';

export interface WebProviderStatus {
  provider: WebProviderId;
  display_name: string;
  description: string;
  configured: boolean;
  supports_full_text: boolean;
}

export interface UserAiPreference {
  default_web_provider: WebProviderId;
  web_search_enabled: boolean;
  voice_read_aloud_enabled: boolean;
  updated_at: string;
}

export interface CitationItem {
  citation_id: number;
  evidence_id: string;
  origin: EvidenceOrigin;
  title: string;
  url?: string | null;
  domain?: string | null;
  provider?: string | null;
}

export interface EvidenceItem {
  evidence_id: string;
  origin: EvidenceOrigin;
  title: string;
  summary: string;
  source_reference?: string | null;
  url?: string | null;
  domain?: string | null;
  provider?: string | null;
  published_at?: string | null;
  retrieved_at?: string | null;
  excerpt?: string | null;
  content_available: boolean;
  is_confirmed_source: boolean;
  meta: Record<string, unknown>;
}

export interface ChatBillDraftAction {
  action_type: 'create_bill';
  bill_name: string;
  bill_category: string;
  provider_name?: string | null;
  bill_type: 'one_time' | 'recurring';
  frequency?: 'weekly' | 'monthly' | 'quarterly' | 'half_yearly' | 'yearly' | 'custom' | null;
  expected_amount?: string | number | null;
  currency: string;
  due_date: string;
  description?: string | null;
  missing_fields?: string[];
  requires_user_confirmation: boolean;
}

export interface ChatTransactionDraftAction {
  action_type: 'create_transaction';
  transcript: string;
  transaction_type: 'expense' | 'income';
  amount?: string | number | null;
  currency: string;
  category_id?: string | null;
  category_name?: string | null;
  account_id?: string | null;
  account_name?: string | null;
  description?: string | null;
  merchant_payee?: string | null;
  transaction_date: string;
  missing_fields?: string[];
  requires_user_confirmation: boolean;
}

export type ChatDraftAction = ChatBillDraftAction | ChatTransactionDraftAction | Record<string, unknown>;

export interface AiMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  provider_used?: string | null;
  llm_model?: string | null;
  web_search_used: boolean;
  tools_invoked: string[];
  citations: CitationItem[];
  evidence_items: EvidenceItem[];
  draft_action?: ChatDraftAction | null;
  status: string;
  error_message?: string | null;
  created_at: string;
}

export interface AiConversationSummary {
  id: string;
  title: string;
  preferred_provider?: WebProviderId | null;
  web_search_enabled: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface AiConversationDetail extends AiConversationSummary {
  messages: AiMessage[];
}

export interface VoiceExpenseDraft {
  transcript: string;
  transaction_type: 'expense' | 'income';
  amount?: string | number | null;
  currency: string;
  category_id?: string | null;
  category_name?: string | null;
  account_id?: string | null;
  account_name?: string | null;
  description?: string | null;
  merchant_payee?: string | null;
  transaction_date: string;
  missing_fields: string[];
  requires_user_confirmation: boolean;
  notes?: string | null;
}

export interface RagReindexResult {
  documents_scanned: number;
  chunks_indexed: number;
  chunks_removed: number;
}
