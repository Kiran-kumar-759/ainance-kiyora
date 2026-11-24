export interface HealthResponse {
  status: string;
  app: string;
  environment: string;
  version: string;
  timestamp: string;
}

export interface DatabaseReadiness {
  ready: boolean;
  status: 'connected' | 'disconnected' | 'error';
  database_name: string | null;
  latency_ms: number;
  error: string | null;
}

export interface ReadinessResponse {
  status: 'ready' | 'degraded';
  database: DatabaseReadiness;
  environment: string;
  timestamp: string;
}

export interface PlatformInfo {
  app_name: string;
  version: string;
  phase: string;
  target_market: string;
  primary_currency: string;
  fiscal_year_cycle: string;
  environment: string;
  database_connected: boolean;
  database_name: string | null;
  settings_count: number;
  timestamp: string;
}

export interface SystemStatusState {
  health: HealthResponse | null;
  readiness: ReadinessResponse | null;
  platform: PlatformInfo | null;
  isLoading: boolean;
  error: string | null;
  backendReachable: boolean;
  databaseReady: boolean;
  lastChecked: Date | null;
}
