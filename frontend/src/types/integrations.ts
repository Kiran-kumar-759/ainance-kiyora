export type IntegrationCategory =
  | 'banking'
  | 'email'
  | 'sms'
  | 'ai'
  | 'web_research'
  | 'notifications';

export type IntegrationStatus =
  | 'connected'
  | 'available'
  | 'configured_not_connected'
  | 'unavailable'
  | 'error'
  | 'planned';

export interface IntegrationItem {
  provider_id: string;
  name: string;
  category: IntegrationCategory;
  description: string;
  status: IntegrationStatus;
  configured: boolean;
  connected: boolean;
  available: boolean;
  is_planned: boolean;
  is_preferred: boolean;
  can_test: boolean;
  can_connect: boolean;
  can_disconnect: boolean;
  capabilities: string[];
  required_env_vars: string[];
  last_sync_or_test_at: string | null;
  last_error: string | null;
  safe_metadata: Record<string, unknown>;
}

export interface IntegrationConnectionSummary {
  connection_id: string;
  connection_type: 'banking' | 'email';
  provider_id: string;
  display_name: string;
  status: string;
  account_or_email: string | null;
  linked_accounts_count: number;
  scopes: string[];
  token_expires_at: string | null;
  last_sync_at: string | null;
  last_error: string | null;
  can_disconnect: boolean;
}

export interface IntegrationsOverview {
  total_integrations: number;
  configured_count: number;
  connected_count: number;
  unavailable_count: number;
  attention_required_count: number;
  planned_count: number;
  preferred_web_provider: 'langsearch' | 'firecrawl' | 'tavily';
  web_search_enabled: boolean;
  integrations: IntegrationItem[];
  connections: IntegrationConnectionSummary[];
}

export interface IntegrationTestResult {
  provider_id: string;
  status: 'ok' | 'unavailable' | 'error' | 'rate_limited' | 'timeout';
  success: boolean;
  message: string;
  latency_ms: number | null;
  checked_at: string;
  details: Record<string, unknown>;
}

export interface IntegrationDisconnectResult {
  connection_id: string;
  connection_type: 'banking' | 'email';
  status: string;
  message: string;
}
