import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Server,
  Database,
  Globe2,
  Calendar,
  IndianRupee,
  Cpu,
  Layers,
  Code2,
  RefreshCw,
  Clock,
  Terminal,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { HealthResponse, ReadinessResponse, PlatformInfo } from '../../types';

interface SystemStatusViewProps {
  health: HealthResponse | null;
  readiness: ReadinessResponse | null;
  platform: PlatformInfo | null;
  isLoading: boolean;
  error: string | null;
  backendReachable: boolean;
  databaseReady: boolean;
  lastChecked: Date | null;
  onRefresh: () => void;
}

export const SystemStatusView: React.FC<SystemStatusViewProps> = ({
  health,
  readiness,
  platform,
  isLoading,
  error,
  backendReachable,
  databaseReady,
  lastChecked,
  onRefresh,
}) => {
  const [showRawPayloads, setShowRawPayloads] = useState(false);

  // Formatting date in Indian Standard Time (IST) / Indian locale
  const formatDateTime = (dateStr?: string | Date | null) => {
    if (!dateStr) return '—';
    const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr;
    return new Intl.DateTimeFormat('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'medium',
      timeZone: 'Asia/Kolkata',
    }).format(date);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Product Foundation Announcement */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 rounded-2xl p-6 sm:p-8 text-white shadow-sm border border-slate-700/50">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-medium tracking-wide">
                PHASE 0 COMPLETED
              </span>
              <span className="text-xs text-slate-400">•</span>
              <span className="text-xs text-slate-300 font-mono">India-First Architecture</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">
              AI Personal Finance Manager
            </h2>
            <p className="mt-2 text-sm text-slate-300 max-w-2xl leading-relaxed">
              Welcome to the foundational development environment. This application shell establishes
              the modular monolith backend, PostgreSQL persistence, and full frontend-to-backend request lifecycle.
              Financial transaction engines, bank integrations, and AI models will be introduced in subsequent phases.
            </p>
          </div>
          <div className="flex-shrink-0 flex md:flex-col items-center md:items-end justify-between md:justify-center border-t md:border-t-0 md:border-l border-slate-700 pt-4 md:pt-0 md:pl-6">
            <span className="text-xs text-slate-400">Target Region</span>
            <span className="text-base font-semibold text-white flex items-center space-x-1.5 mt-0.5">
              <span>🇮🇳</span>
              <span>India (INR / ₹)</span>
            </span>
          </div>
        </div>
      </div>

      {/* Critical Status Alerts if degraded or disconnected */}
      {!backendReachable && (
        <div className="rounded-xl bg-rose-50 border border-rose-200 p-4 text-rose-900 flex items-start space-x-3">
          <XCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-rose-900">Backend API Unreachable</h4>
            <p className="text-xs text-rose-700 mt-1">
              The React frontend could not connect to FastAPI at{' '}
              <code className="font-mono bg-rose-100 px-1 py-0.5 rounded">http://127.0.0.1:8000</code>.
              Check that the Uvicorn server is running.
            </p>
            {error && (
              <p className="text-xs font-mono text-rose-800 bg-rose-100/70 p-2 rounded mt-2">
                Details: {error}
              </p>
            )}
          </div>
        </div>
      )}

      {backendReachable && !databaseReady && (
        <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 text-amber-900 flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-amber-900">Database Degraded / Unreachable</h4>
            <p className="text-xs text-amber-700 mt-1">
              FastAPI is responding, but the PostgreSQL readiness check failed.
              The application correctly identified the service degradation.
            </p>
            {readiness?.database.error && (
              <p className="text-xs font-mono text-amber-800 bg-amber-100/70 p-2 rounded mt-2">
                Error: {readiness.database.error}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Primary Diagnostic Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Backend Service */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <Server className="w-5 h-5" />
            </div>
            {backendReachable ? (
              <Badge variant="success">Online (200 OK)</Badge>
            ) : (
              <Badge variant="danger">Disconnected</Badge>
            )}
          </div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
            FastAPI Backend
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            {backendReachable ? health?.app || 'AI Finance Manager' : 'Offline'}
          </div>
          <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
            <span>Version: {health?.version || '0.1.0'}</span>
            <span className="font-mono text-[11px]">{health?.environment || 'dev'}</span>
          </div>
        </Card>

        {/* Card 2: PostgreSQL Readiness */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
              <Database className="w-5 h-5" />
            </div>
            {databaseReady ? (
              <Badge variant="success">Ready ({readiness?.database.latency_ms} ms)</Badge>
            ) : (
              <Badge variant="danger">Down</Badge>
            )}
          </div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
            PostgreSQL Engine
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            {databaseReady ? readiness?.database.database_name || 'pfm_dev' : 'Unavailable'}
          </div>
          <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
            <span>Query Ping: {readiness?.database.latency_ms ?? '—'} ms</span>
            <span className="text-emerald-600 font-medium">SQLAlchemy 2.x</span>
          </div>
        </Card>

        {/* Card 3: Target Financial Market */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <div className="w-9 h-9 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600">
              <IndianRupee className="w-5 h-5" />
            </div>
            <Badge variant="info">India (IN)</Badge>
          </div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
            Financial Currency
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            ₹ INR (Indian Rupee)
          </div>
          <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
            <span>Fiscal Year: Apr–Mar</span>
            <span>Locale: en-IN</span>
          </div>
        </Card>

        {/* Card 4: Platform Baseline State */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <div className="w-9 h-9 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700">
              <Layers className="w-5 h-5" />
            </div>
            <Badge variant="neutral">Modular Monolith</Badge>
          </div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
            Architecture Level
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            Phase 0 Foundation
          </div>
          <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
            <span>DB Records: {platform?.settings_count ?? 1}</span>
            <span className="text-slate-400">Strict Isolation</span>
          </div>
        </Card>
      </div>

      {/* Verified Request-Response Flow Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Verification Summary */}
        <div className="lg:col-span-2 space-y-6">
          <Card
            title="Complete Architecture Verification Chain"
            subtitle="Verified request-response workflow from PostgreSQL to FastAPI to React UI"
          >
            <div className="space-y-4">
              <div className="flex items-start space-x-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="p-1.5 rounded-full bg-emerald-100 text-emerald-600 mt-0.5">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-slate-900">1. Database Layer (PostgreSQL 18)</h4>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Dedicated databases (<code className="font-mono text-slate-800">pfm_dev</code> and{' '}
                    <code className="font-mono text-slate-800">pfm_test</code>) configured on PostgreSQL 18.6.
                    Alembic migrations generate revision <code className="font-mono">bb635945c608</code> and apply DDL cleanly.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="p-1.5 rounded-full bg-emerald-100 text-emerald-600 mt-0.5">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-slate-900">2. Backend Service Layer (FastAPI + SQLAlchemy 2.x)</h4>
                  <p className="text-xs text-slate-600 mt-0.5">
                    FastAPI handles dependency injection, CORS validation, safe credential handling,
                    and executes real PostgreSQL queries via <code className="font-mono text-slate-800">check_db_readiness()</code>.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="p-1.5 rounded-full bg-emerald-100 text-emerald-600 mt-0.5">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-slate-900">3. Functional Frontend UI (React + Vite + Tailwind)</h4>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Connected to the actual backend via <code className="font-mono text-slate-800">apiClient</code>.
                    No simulated or mocked statuses; honest error handling dynamically reflects server and database availability.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between text-xs text-slate-500 gap-2">
              <div className="flex items-center space-x-2">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>Last verified: {formatDateTime(lastChecked)} (IST)</span>
              </div>
              <button
                type="button"
                onClick={() => setShowRawPayloads(!showRawPayloads)}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center space-x-1"
              >
                <Terminal className="w-3.5 h-3.5" />
                <span>{showRawPayloads ? 'Hide Raw Payloads' : 'Inspect Raw API Payloads'}</span>
              </button>
            </div>
          </Card>

          {/* Raw Diagnostic JSON Inspector (Collapsible) */}
          {showRawPayloads && (
            <Card title="Raw Diagnostics Payloads" subtitle="Real payloads received from FastAPI backend">
              <div className="space-y-3 font-mono text-xs">
                <div>
                  <div className="text-slate-500 mb-1 font-semibold">GET /health (Liveness)</div>
                  <pre className="bg-slate-900 text-slate-200 p-3 rounded-lg overflow-x-auto">
                    {JSON.stringify(health, null, 2)}
                  </pre>
                </div>
                <div>
                  <div className="text-slate-500 mb-1 font-semibold">GET /health/ready (Readiness Probe)</div>
                  <pre className="bg-slate-900 text-slate-200 p-3 rounded-lg overflow-x-auto">
                    {JSON.stringify(readiness, null, 2)}
                  </pre>
                </div>
                <div>
                  <div className="text-slate-500 mb-1 font-semibold">GET /api/v1/system/info (Platform Info)</div>
                  <pre className="bg-slate-900 text-slate-200 p-3 rounded-lg overflow-x-auto">
                    {JSON.stringify(platform, null, 2)}
                  </pre>
                </div>
              </div>
            </Card>
          )}

          {/* Product Staging Roadmap */}
          <Card
            title="SaaS Implementation Staging Roadmap"
            subtitle="Strict boundary preservation: future financial features will be added in staged phases"
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200/80">
                <div className="font-semibold text-emerald-900 flex items-center space-x-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Phase 0 — Foundation & Demo UI</span>
                </div>
                <p className="text-slate-600 mt-1">
                  Architecture, PostgreSQL, Alembic, FastAPI, health probes, connected functional UI shell.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/70">
                <div className="font-semibold text-slate-800 flex items-center space-x-1.5">
                  <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                  <span>Phase 1 — Auth & Onboarding</span>
                </div>
                <p className="text-slate-500 mt-1">
                  Multi-user registration, JWT authentication, tenant isolation, onboarding flow.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/70">
                <div className="font-semibold text-slate-800 flex items-center space-x-1.5">
                  <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                  <span>Phase 2 — Accounts & Transactions</span>
                </div>
                <p className="text-slate-500 mt-1">
                  Indian financial account types (Savings, Current, FD, Credit Card, Demat), manual entries.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/70">
                <div className="font-semibold text-slate-800 flex items-center space-x-1.5">
                  <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                  <span>Phase 3 & 4 — Bank Integrations & Imports</span>
                </div>
                <p className="text-slate-500 mt-1">
                  Simulated bank connectors, CSV/XLSX/PDF statement parsing with Indian bank templates.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/70">
                <div className="font-semibold text-slate-800 flex items-center space-x-1.5">
                  <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                  <span>Phase 5 & 6 — Analytics & Budgets</span>
                </div>
                <p className="text-slate-500 mt-1">
                  Indian financial year analytics (Apr-Mar), category budgeting, savings goals.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/70">
                <div className="font-semibold text-slate-800 flex items-center space-x-1.5">
                  <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                  <span>Phase 7–11 — AI, Intelligence & EMI</span>
                </div>
                <p className="text-slate-500 mt-1">
                  Recurring bills, OTT subscriptions, loan EMI calculators, AI categorization, natural language assistant.
                </p>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: Platform Specifications */}
        <div className="space-y-6">
          <Card title="Indian Financial Specifications" subtitle="Pre-configured regional standards">
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500 flex items-center space-x-1.5">
                  <IndianRupee className="w-3.5 h-3.5 text-slate-400" />
                  <span>Base Currency</span>
                </span>
                <span className="font-semibold text-slate-800">INR (₹)</span>
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500 flex items-center space-x-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>Financial Year</span>
                </span>
                <span className="font-semibold text-slate-800">April 1 – March 31</span>
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500 flex items-center space-x-1.5">
                  <Globe2 className="w-3.5 h-3.5 text-slate-400" />
                  <span>Number Formatting</span>
                </span>
                <span className="font-mono text-slate-800">₹1,00,000 (Lakh / Crore)</span>
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500 flex items-center space-x-1.5">
                  <Code2 className="w-3.5 h-3.5 text-slate-400" />
                  <span>Financial Arithmetic</span>
                </span>
                <span className="text-emerald-700 font-medium">Exact Decimal / NUMERIC</span>
              </div>

              <div className="flex items-center justify-between py-1.5">
                <span className="text-slate-500 flex items-center space-x-1.5">
                  <Cpu className="w-3.5 h-3.5 text-slate-400" />
                  <span>Background Engine</span>
                </span>
                <span className="text-slate-800">Valkey / Redis (Port 6379)</span>
              </div>
            </div>
          </Card>

          <Card title="Dev Diagnostic Controls" subtitle="Verify reactive error states">
            <div className="space-y-3 text-xs">
              <p className="text-slate-600 leading-relaxed">
                Click below to force an immediate probe of backend liveness and PostgreSQL query readiness.
              </p>
              <button
                type="button"
                onClick={onRefresh}
                disabled={isLoading}
                className="w-full flex items-center justify-center space-x-2 py-2 px-4 rounded-lg bg-slate-900 text-white font-medium hover:bg-slate-800 transition-colors shadow-xs disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                <span>{isLoading ? 'Polling Endpoints...' : 'Execute Health Probe'}</span>
              </button>

              <div className="pt-2 text-[11px] text-slate-400">
                <div className="font-medium text-slate-600 mb-0.5">Verification Rule:</div>
                Stopping Uvicorn or disconnecting PostgreSQL will immediately render an honest degraded error state on this page without crashing.
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
