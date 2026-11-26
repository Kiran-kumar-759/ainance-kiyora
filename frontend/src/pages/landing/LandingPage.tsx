import React from 'react';
import {
  ArrowRight,
  BarChart3,
  BellRing,
  Bot,
  CalendarDays,
  CheckCircle2,
  CreditCard,
  FileSpreadsheet,
  FileText,
  Landmark,
  Lock,
  MailCheck,
  RefreshCw,
  ScanText,
  Server,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Wallet,
  XCircle,
} from 'lucide-react';
import { SystemStatusState } from '../../types';

interface LandingPageProps {
  health: SystemStatusState['health'];
  readiness: SystemStatusState['readiness'];
  platform: SystemStatusState['platform'];
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  onNavigate: (view: string) => void;
  isAuthenticated?: boolean;
}

const FEATURES = [
  {
    icon: Wallet,
    title: 'Multi-Account & Liability Ledger',
    desc: 'Separate liquid balances across savings, wallets, and investments from credit card dues cleanly.',
    accent: 'text-indigo-600 bg-indigo-50',
  },
  {
    icon: FileSpreadsheet,
    title: 'Smart Statement Imports',
    desc: 'Upload CSV & XLSX bank statements with custom column mapping, transfer handling & deduplication.',
    accent: 'text-blue-600 bg-blue-50',
  },
  {
    icon: BarChart3,
    title: 'Deep Cashflow Analytics',
    desc: 'Interactive period comparisons, category drill-downs, savings rates, and printable reports.',
    accent: 'text-violet-600 bg-violet-50',
  },
  {
    icon: CalendarDays,
    title: 'Bills & Recurring Schedules',
    desc: 'Track variable utility bills, partial payments, vendor references & recurrence automation.',
    accent: 'text-emerald-600 bg-emerald-50',
  },
  {
    icon: CreditCard,
    title: 'OTT & Subscription Hygiene',
    desc: 'Monitor paid months count, billing cycles, renewal price jumps, and recurring merchant candidates.',
    accent: 'text-indigo-600 bg-indigo-50',
  },
  {
    icon: Landmark,
    title: 'Loans, EMIs & Prepayments',
    desc: 'Full amortization curves, floating rate adjustments, and what-if prepayment interest savings.',
    accent: 'text-blue-600 bg-blue-50',
  },
  {
    icon: ScanText,
    title: 'Document OCR & Gmail Ingestion',
    desc: 'Two-panel receipt inspection powered by RapidOCR plus read-only Gmail bill extraction.',
    accent: 'text-violet-600 bg-violet-50',
  },
  {
    icon: BellRing,
    title: 'Reminders & Delivery Logs',
    desc: 'Automated in-app & SMTP reminder schedules per commitment without ever auto-marking bills paid.',
    accent: 'text-amber-600 bg-amber-50',
  },
  {
    icon: TrendingUp,
    title: 'Cashflow Forecasting & Scenarios',
    desc: 'Multi-horizon projections with anomaly flags and walk-forward forecast accuracy metrics.',
    accent: 'text-indigo-600 bg-indigo-50',
  },
  {
    icon: Bot,
    title: 'AI Finance Assistant (RAG + Web)',
    desc: 'Strict separation of your PostgreSQL records, uploaded OCR docs, and LangSearch/Firecrawl/Tavily research.',
    accent: 'text-violet-600 bg-violet-50',
  },
];

export const LandingPage: React.FC<LandingPageProps> = ({
  health,
  readiness,
  platform,
  isLoading,
  error,
  onRefresh,
  onNavigate,
  isAuthenticated = false,
}) => {
  const backendReachable = Boolean(health && health.status === 'ok');
  const databaseReady = Boolean(readiness?.database?.ready);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Sticky Navigation Header */}
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/85 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center text-white font-bold text-base shadow-sm">
              ₹
            </div>
            <div>
              <span className="text-sm font-bold text-slate-900 block leading-tight">
                AI Personal Finance Manager
              </span>
              <span className="text-[11px] font-medium text-indigo-600">
                India-First • FinSight AI Platform
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-6 text-xs font-semibold text-slate-600">
            <a href="#features" className="hover:text-indigo-600 transition-colors">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-indigo-600 transition-colors">
              How It Works
            </a>
            <a href="#ai-assistant" className="hover:text-indigo-600 transition-colors">
              AI Assistant
            </a>
            <a href="#security" className="hover:text-indigo-600 transition-colors">
              Security & Status
            </a>
          </nav>

          <div className="flex items-center gap-2.5">
            {isAuthenticated ? (
              <button
                type="button"
                onClick={() => onNavigate('dashboard')}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-colors"
              >
                <span>Open Dashboard</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => onNavigate('login')}
                  className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
                >
                  Login
                </button>
                <button
                  type="button"
                  onClick={() => onNavigate('register')}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-xs font-semibold shadow-sm transition-all"
                >
                  <span>Get Started</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section with Selective Glassmorphism */}
      <section className="relative overflow-hidden bg-navy-950 text-white pt-16 pb-20 sm:pt-24 sm:pb-28">
        <div
          aria-hidden="true"
          className="absolute -top-32 -left-24 w-[480px] h-[480px] rounded-full bg-indigo-600/25 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-32 right-0 w-[440px] h-[440px] rounded-full bg-violet-600/20 blur-3xl"
        />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6 space-y-6 animate-slideUp">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/15 border border-indigo-400/30 text-indigo-200 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-indigo-300" />
              <span>Built for Indian Households & Working Professionals</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-[1.12] text-white">
              Take Control of Your Money.{' '}
              <span className="bg-gradient-to-r from-indigo-300 via-blue-200 to-violet-300 bg-clip-text text-transparent">
                Understand Every Rupee.
              </span>
            </h1>

            <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-xl">
              Track bank accounts, UPI expenses, OTT subscriptions, loans, EMIs, and utility
              bills in one PostgreSQL-backed workspace — complete with local document OCR, Gmail
              bill ingestion, cashflow forecasting, and an auditable AI finance assistant.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                type="button"
                onClick={() => onNavigate(isAuthenticated ? 'dashboard' : 'register')}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-500 hover:from-indigo-400 hover:to-violet-400 text-white text-sm font-semibold shadow-lg shadow-indigo-950/50 transition-all"
              >
                <span>{isAuthenticated ? 'Continue to Workspace' : 'Create Free Account'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => onNavigate('login')}
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-white/10 hover:bg-white/15 border border-white/15 text-white text-sm font-semibold backdrop-blur-sm transition-colors"
              >
                <span>Sign In</span>
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-800/90 text-xs">
              <div>
                <p className="font-bold text-white">INR-Native</p>
                <p className="text-slate-400 mt-0.5">Apr–Mar FY & DD/MM/YYYY</p>
              </div>
              <div>
                <p className="font-bold text-white">Honest Ledger</p>
                <p className="text-slate-400 mt-0.5">Liabilities never inflate cash</p>
              </div>
              <div>
                <p className="font-bold text-white">Zero Data Fabrication</p>
                <p className="text-slate-400 mt-0.5">Every insight cites its source</p>
              </div>
            </div>
          </div>

          {/* Illustrative Preview Glass Card */}
          <div className="lg:col-span-6">
            <div className="glass-dark rounded-2xl p-5 sm:p-6 space-y-4">
              <div className="flex items-center justify-between gap-2 border-b border-slate-700/70 pb-3">
                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-300">
                    Illustrative Interface Preview
                  </span>
                  <h2 className="text-sm font-bold text-white">Workspace Snapshot</h2>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-200 border border-amber-400/30">
                  Sample Preview Only
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-slate-900/90 border border-slate-700/80 p-3.5">
                  <p className="text-[11px] text-slate-400">Liquid Cash & Savings</p>
                  <p className="text-lg font-bold text-white mt-1 tabular-nums">₹4,82,500</p>
                  <p className="text-[11px] text-emerald-400 mt-1">Across linked accounts</p>
                </div>
                <div className="rounded-xl bg-slate-900/90 border border-slate-700/80 p-3.5">
                  <p className="text-[11px] text-slate-400">Tracked Obligations</p>
                  <p className="text-lg font-bold text-white mt-1 tabular-nums">₹28,490</p>
                  <p className="text-[11px] text-indigo-300 mt-1">Bills • EMIs • OTT Plans</p>
                </div>
              </div>

              <div className="rounded-xl bg-slate-900/80 border border-slate-700/80 p-3.5 space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-medium flex items-center gap-1.5">
                    <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    AI Assistant Grounded Answer
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-200">
                    Ledger + Web Citation
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  “You have paid Netflix Standard for 4 months cleanly. Your BESCOM bill draft for
                  ₹1,200 is ready for your confirmation or automatic saving.”
                </p>
              </div>

              <p className="text-[11px] text-slate-400 text-center">
                Connect accounts or upload statements after signing in to see your live numbers.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Capabilities Grid */}
      <section id="features" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <p className="text-xs font-bold uppercase tracking-widest text-indigo-600">
            Complete Financial Suite
          </p>
          <h2 className="mt-2 text-2xl sm:text-3xl font-bold text-slate-900">
            Everything needed to master daily cashflow & long-term obligations
          </h2>
          <p className="mt-3 text-sm text-slate-600">
            Designed cleanly without cluttered dashboards or fabricated forecasts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="rounded-2xl bg-white border border-slate-200/80 p-5 shadow-card hover:shadow-elevated hover:-translate-y-0.5 transition-all duration-200"
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${f.accent}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="mt-4 text-sm font-bold text-slate-900">{f.title}</h3>
                <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* How It Works & AI Architecture */}
      <section id="how-it-works" className="bg-white border-y border-slate-200/80 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
          <div className="lg:col-span-6 space-y-6">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-indigo-600">
                Quick Onboarding
              </p>
              <h2 className="mt-2 text-2xl font-bold text-slate-900">Up and running in minutes</h2>
            </div>

            <div className="space-y-4">
              {[
                {
                  step: '01',
                  title: 'Configure Your India-First Preferences',
                  desc: 'Set INR formatting, Asia/Kolkata timezone, and notification preferences in onboarding.',
                },
                {
                  step: '02',
                  title: 'Import Statements, Bills, or Connect Gmail',
                  desc: 'Upload CSV/XLSX statements, run local RapidOCR on bills, or authorize read-only Gmail sync.',
                },
                {
                  step: '03',
                  title: 'Track Cashflow, Forecasts & AI Guidance',
                  desc: 'Monitor cash vs liabilities, dispatch scheduled reminders, and query AI with source citations.',
                },
              ].map((item) => (
                <div
                  key={item.step}
                  className="flex gap-4 p-4 rounded-2xl bg-slate-50 border border-slate-200/70"
                >
                  <span className="text-sm font-extrabold text-indigo-600 tabular-nums shrink-0">
                    {item.step}
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">{item.title}</h3>
                    <p className="text-xs text-slate-600 mt-1 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div id="ai-assistant" className="lg:col-span-6">
            <div className="rounded-2xl glass-accent p-6 sm:p-7 space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-indigo-600 text-white">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Verifiable AI Finance Assistant
                  </h3>
                  <p className="text-xs text-slate-600">
                    Groq inference + deterministic PostgreSQL queries + live web search
                  </p>
                </div>
              </div>

              <ul className="space-y-2.5 text-xs text-slate-700">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Clear Source Separation:</strong> Personal financial records, OCR
                    documents, and external web research appear in distinct citation sections.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Choice of Web Research Providers:</strong> Switch between LangSearch,
                    Firecrawl, and Tavily cleanly per conversation.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Draft Review or Auto-Execution:</strong> Require manual bill/OTT
                    confirmation or enable Auto-Execute Actions cleanly from the chat header.
                  </span>
                </li>
              </ul>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => onNavigate(isAuthenticated ? 'assistant' : 'register')}
                  className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-700 hover:text-indigo-900"
                >
                  <span>Try AI Assistant</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Security & Live Platform Foundation / System Readiness */}
      <section id="security" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 space-y-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Security Engineering Commitments */}
          <div className="lg:col-span-6 space-y-4">
            <p className="text-xs font-bold uppercase tracking-widest text-indigo-600">
              Engineering & Privacy Controls
            </p>
            <h2 className="text-2xl font-bold text-slate-900">
              Built for multi-tenant isolation & verifiable state
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
              Every API route validates session cookies, enforces CSRF protection on state-changing
              calls, scopes queries strictly by authenticated `user_id`, and stores credentials using
              Argon2id hashing and encrypted OAuth tokens.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              {[
                { icon: Lock, label: 'HttpOnly Sessions + CSRF', sub: 'Double-submit token enforcement' },
                { icon: ShieldCheck, label: 'Argon2id Passwords', sub: 'Modern memory-hard hashing' },
                { icon: MailCheck, label: 'Scoped Gmail Read-Only', sub: 'Strict OAuth state & PKCE verification' },
                { icon: FileText, label: 'Private Document Vault', sub: 'No unauthenticated direct URLs' },
              ].map((s) => {
                const Icon = s.icon;
                return (
                  <div key={s.label} className="rounded-xl bg-white border border-slate-200 p-3.5 shadow-card">
                    <div className="flex items-center gap-2 text-slate-900 font-semibold text-xs">
                      <Icon className="w-4 h-4 text-indigo-600" />
                      <span>{s.label}</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">{s.sub}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Live System Foundation & Readiness Panel (Preserves Phase 0 Health Readout cleanly) */}
          <div className="lg:col-span-6">
            <div className="rounded-2xl bg-white border border-slate-200 shadow-card p-5 sm:p-6 space-y-4">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-600">
                    System Foundation
                  </span>
                  <h3 className="text-base font-bold text-slate-900">Live Backend & Database Readiness</h3>
                </div>
                <button
                  type="button"
                  onClick={onRefresh}
                  disabled={isLoading}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs font-semibold text-slate-700"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
                  <span>Refresh</span>
                </button>
              </div>

              {error && !backendReachable && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-2.5">
                  <XCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <div className="text-xs">
                    <p className="font-bold text-rose-900">Backend API Unreachable</p>
                    <p className="text-rose-700 mt-0.5">
                      The React frontend could not connect to FastAPI: {error}
                    </p>
                  </div>
                </div>
              )}

              {backendReachable && readiness && !databaseReady && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex items-start gap-2.5">
                  <XCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div className="text-xs">
                    <p className="font-bold text-amber-900">Database Degraded / Unreachable</p>
                    <p className="text-amber-800 mt-0.5">
                      FastAPI is responding, but the PostgreSQL readiness check failed:{' '}
                      {readiness.database.error || 'Unknown error'}
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="rounded-xl bg-slate-50 border border-slate-200/80 p-3.5">
                  <span className="text-slate-500 flex items-center gap-1.5 font-medium">
                    <Server className="w-3.5 h-3.5 text-indigo-600" />
                    FastAPI Service
                  </span>
                  <p className="mt-1 font-bold text-slate-900">
                    {isLoading
                      ? 'Checking connection...'
                      : backendReachable
                      ? `Connected (${health?.version || 'live'})`
                      : 'Offline'}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-50 border border-slate-200/80 p-3.5">
                  <span className="text-slate-500 flex items-center gap-1.5 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    PostgreSQL Engine
                  </span>
                  <p className="mt-1 font-bold text-slate-900">
                    {isLoading
                      ? 'Checking readiness...'
                      : databaseReady
                      ? `Ready (${readiness?.database.latency_ms ?? 0} ms)`
                      : 'Disconnected'}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-50 border border-slate-200/80 p-3.5">
                  <span className="text-slate-500 font-medium">Primary Currency</span>
                  <p className="mt-1 font-bold text-slate-900">
                    {platform?.primary_currency === 'INR' ? 'INR (Indian Rupee)' : platform?.primary_currency || 'INR (Indian Rupee)'}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-50 border border-slate-200/80 p-3.5">
                  <span className="text-slate-500 font-medium">Fiscal Year Cycle</span>
                  <p className="mt-1 font-bold text-slate-900">
                    {platform?.fiscal_year_cycle === 'April - March'
                      ? 'April 1 – March 31'
                      : platform?.fiscal_year_cycle || 'April 1 – March 31'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA & Footer */}
      <footer className="bg-navy-900 text-slate-300 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white font-bold flex items-center justify-center">
              ₹
            </div>
            <span>AI Personal Finance Manager — India-First SaaS Workspace</span>
          </div>
          <div className="flex items-center gap-5 text-slate-400">
            <button type="button" onClick={() => onNavigate('login')} className="hover:text-white">
              Sign In
            </button>
            <button type="button" onClick={() => onNavigate('register')} className="hover:text-white">
              Create Account
            </button>
            {isAuthenticated && (
              <button type="button" onClick={() => onNavigate('dashboard')} className="hover:text-white">
                Dashboard
              </button>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
};
