import React, { useEffect, useRef } from 'react';
import { RefreshCw } from 'lucide-react';
import { SystemStatusState } from '../../types';
import './landing.css';

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
  const rootRef = useRef<HTMLDivElement | null>(null);
  const heroRef = useRef<HTMLElement | null>(null);
  const glassRef = useRef<HTMLDivElement | null>(null);

  const backendReachable = Boolean(health && health.status === 'ok');
  const databaseReady = Boolean(readiness?.database?.ready);

  useEffect(() => {
    const root = rootRef.current;
    const hero = heroRef.current;
    const glass = glassRef.current;
    if (!root || typeof window === 'undefined') return;

    const reduceMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const onWindowMove = (e: PointerEvent) => {
      root.style.setProperty('--mx', `${e.clientX}px`);
      root.style.setProperty('--my', `${e.clientY}px`);
    };

    window.addEventListener('pointermove', onWindowMove, { passive: true });

    const glowTargets = root.querySelectorAll<HTMLElement>(
      '.fs-card, .fs-proof > div, .fs-gc, .fs-band > div, .fs-glass'
    );
    const cardCleanups: Array<() => void> = [];
    glowTargets.forEach((el) => {
      const onCardMove = (e: PointerEvent) => {
        const b = el.getBoundingClientRect();
        el.style.setProperty('--x', `${e.clientX - b.left}px`);
        el.style.setProperty('--y', `${e.clientY - b.top}px`);
      };
      el.addEventListener('pointermove', onCardMove);
      cardCleanups.push(() => el.removeEventListener('pointermove', onCardMove));
    });

    let heroCleanup: (() => void) | undefined;
    if (glass && hero && !reduceMotion) {
      const onHeroMove = (e: PointerEvent) => {
        const b = glass.getBoundingClientRect();
        const dx = (e.clientX - (b.left + b.width / 2)) / (window.innerWidth / 2 || 1);
        const dy = (e.clientY - (b.top + b.height / 2)) / (window.innerHeight / 2 || 1);
        glass.style.setProperty('--ry', `${Math.max(-1, Math.min(1, dx)) * 9}deg`);
        glass.style.setProperty('--rx', `${Math.max(-1, Math.min(1, dy)) * -7}deg`);
      };
      const onHeroLeave = () => {
        glass.style.setProperty('--ry', '0deg');
        glass.style.setProperty('--rx', '0deg');
      };
      hero.addEventListener('pointermove', onHeroMove);
      hero.addEventListener('pointerleave', onHeroLeave);
      heroCleanup = () => {
        hero.removeEventListener('pointermove', onHeroMove);
        hero.removeEventListener('pointerleave', onHeroLeave);
      };
    }

    return () => {
      window.removeEventListener('pointermove', onWindowMove);
      cardCleanups.forEach((fn) => fn());
      heroCleanup?.();
    };
  }, []);

  const handleRouteClick =
    (view: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      onNavigate(view);
    };

  return (
    <div ref={rootRef} className="fs-landing">
      <div className="fs-amb" aria-hidden="true" />

      <header ref={heroRef} className="fs-hero">
        <nav className="fs-nav" aria-label="Main">
          <a
            className="fs-logo"
            href="#top"
            aria-label="FinSight AI — AI Personal Finance Manager"
          >
            <i />
            <span>FinSight AI</span>
          </a>

          <div className="fs-pill">
            <a href="#top">Home</a>
            <a href="#about">About</a>
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <a href="#security">Security</a>
          </div>

          <div className="fs-right">
            {isAuthenticated ? (
              <a
                className="fs-btn-o"
                href="/dashboard"
                onClick={handleRouteClick('dashboard')}
              >
                Open Dashboard
              </a>
            ) : (
              <>
                <a href="/login" onClick={handleRouteClick('login')}>
                  Sign In
                </a>
                <a
                  className="fs-btn-o"
                  href="/register"
                  onClick={handleRouteClick('register')}
                >
                  Get started
                </a>
              </>
            )}
          </div>
        </nav>

        <div className="fs-copy" id="top">
          <span className="fs-eb">
            India-First Personal Finance SaaS • Powered by Verifiable Ledger Data &amp; AI
          </span>
          <h1>
            Take Control of Your Money.
            <br />
            Understand Every Rupee.
          </h1>
          <p className="fs-sub">
            An all-in-one personal finance manager built for Indian households and working
            professionals. Track bank accounts, UPI expenses, utility bills, OTT subscriptions, and
            loan EMIs alongside local OCR receipt scanning, read-only Gmail bill ingestion, cashflow
            forecasting, and a voice-enabled AI advisor grounded in your actual records.
          </p>
          <div className="fs-ctas">
            <a
              className="fs-cta"
              href={isAuthenticated ? '/dashboard' : '/register'}
              onClick={handleRouteClick(isAuthenticated ? 'dashboard' : 'register')}
            >
              {isAuthenticated ? 'Open Dashboard' : 'Get Started Free'} <b>→</b>
            </a>
            {!isAuthenticated && (
              <a className="fs-alt" href="/login" onClick={handleRouteClick('login')}>
                Sign In
              </a>
            )}
          </div>
        </div>

        <div className="fs-stg" aria-hidden="true">
          <div className="fs-po" />
          <div className="fs-bo" />
          <div className="fs-waist" />

          <div className="fs-gc fs-c1">
            <h4>Expenses Report</h4>
            <div className="ring">
              ₹52,252<small>Total expenses</small>
            </div>
          </div>
          <div className="fs-gc fs-c2">
            <h4>Saving Budget</h4>
            <div className="n">₹1,35,352</div>
            <small>updated today</small>
          </div>
          <div className="fs-gc fs-c3">
            <div className="n">₹85,000</div>
            <small>updated today</small>
          </div>
          <div className="fs-gc fs-c4">
            <h4>Emergency</h4>
          </div>
          <div className="fs-gc fs-c5" />
          <div className="fs-gc fs-c6">
            <h4>Transactions</h4>
            <div className="bar" />
            <div className="bar" />
          </div>
          <div className="fs-gc fs-c7">
            <h4>Budgets</h4>
            <div className="bar">Save for a Car</div>
            <div className="bar">Save for Education</div>
            <div className="bar">Vacation Fund</div>
          </div>
          <div className="fs-gc fs-c8">
            <h4>Your Goals</h4>
            <div className="bar">House by the Sea</div>
            <div className="n">₹5,35,200</div>
          </div>

          <div ref={glassRef} className="fs-glass">
            <div className="in">
              <span className="sample-tag">Sample Preview Only</span>
              <div className="l">Total Balance</div>
              <div className="t">
                ₹5,23,734 <span>◉</span>
              </div>
              <div className="row">
                <div>
                  <span>Income</span>
                  <b>₹2,25,222</b>
                </div>
                <div>
                  <span>Expense</span>
                  <b>₹1,12,522</b>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="fs-proof">
        <div>
          <b>INR-Native &amp; IST Ready</b>April–March fiscal year and DD/MM/YYYY formatting
        </div>
        <div>
          <b>Honest Double-Entry Ledger</b>Liabilities never inflate liquid cash balances
        </div>
        <div>
          <b>Evidence-Backed AI</b>Strict separation between your ledger records and web research
        </div>
      </div>

      <section id="about" className="fs-section fs-center">
        <h2>Most finance trackers only look backwards.</h2>
        <p className="fs-lead">
          Most finance trackers only show past expenses or connect blindly to generic chatbots.
          FinSight AI (AI Personal Finance Manager) combines a PostgreSQL-backed personal finance
          ledger with explainable forecasting and a hybrid AI assistant. Every balance, subscription
          cycle, loan EMI, and reminder is verifiable—and when you ask a financial question (like
          whether you can afford a purchase), the AI checks your real bank balances and upcoming
          commitments alongside live market pricing from web research, asking smart follow-up
          questions before giving advice.
        </p>
      </section>

      <section id="features" className="fs-section">
        <h2 className="fs-center">Everything your money touches, in one place</h2>
        <div className="fs-grid">
          <div className="fs-card">
            <div className="fs-ico" />
            <h3>Accounts, Ledger &amp; Credit Isolation</h3>
            <p>
              Manage savings, current, cash, wallet, and credit card accounts cleanly with zero-sum
              internal transfers and explicit separation between liquid assets and card/loan
              liabilities.
            </p>
          </div>
          <div className="fs-card">
            <div className="fs-ico" />
            <h3>Smart Bank Statement Imports</h3>
            <p>
              Upload .csv and .xlsx bank statements with interactive column mapping, validation, and
              duplicate detection before committing to your ledger.
            </p>
          </div>
          <div className="fs-card">
            <div className="fs-ico" />
            <h3>Analytics, Period Comparisons &amp; Reports</h3>
            <p>
              Inspect cashflow trends, savings rate, category drill-downs, and downloadable CSV
              summary reports.
            </p>
          </div>
          <div className="fs-card">
            <div className="fs-ico" />
            <h3>Bills, OTT Subscriptions &amp; Loans/EMIs</h3>
            <p>
              Track one-time and recurring bills, partial payments, OTT renewal cycles with
              paid-months history, loan amortization schedules, interest rate revisions, and what-if
              prepayment simulations.
            </p>
          </div>
          <div className="fs-card">
            <div className="fs-ico" />
            <h3>Reminders &amp; Notification Center</h3>
            <p>
              Schedule and dispatch due alerts across bills, subscriptions, and EMIs with delivery
              logs and SMTP status checks—without ever auto-marking an obligation as paid.
            </p>
          </div>
          <div className="fs-card">
            <div className="fs-ico" />
            <h3>Document OCR &amp; Read-Only Gmail Bill Sync</h3>
            <p>
              Extract amounts, dates, vendors, and GST/invoice fields from uploaded PDFs and
              receipts locally using RapidOCR, or sync vendor bills cleanly via read-only Gmail OAuth
              (2.0 + PKCE) with two-panel human review.
            </p>
          </div>
          <div className="fs-card">
            <div className="fs-ico" />
            <h3>Cashflow Forecasting &amp; Expense Intelligence</h3>
            <p>
              Detect anomalies, discover recurring merchants, and project multi-horizon cashflow (7
              to 365 days) with transparent confidence labels (high / medium / low /
              insufficient_data).
            </p>
          </div>
          <div className="fs-card">
            <div className="fs-ico" />
            <h3>Hybrid AI Finance Assistant &amp; Voice Copilot</h3>
            <p>
              Ask questions via text or voice (16 kHz WAV mic capture + Whisper STT + local WAV Read
              Aloud). Combines PostgreSQL tools, uploaded document RAG, and selectable web search
              providers (Tavily, LangSearch, Firecrawl) with clear [1], [2] citations and
              confirmation-gated (or optional Auto-Execute) bill and subscription drafts.
            </p>
          </div>
        </div>
      </section>

      <section id="how" className="fs-section fs-center">
        <h2>How it works</h2>
        <div className="fs-grid fs-steps" style={{ textAlign: 'left' }}>
          <div className="fs-card">
            <span>1</span>
            <h3>Set Up Your Workspace</h3>
            <p>
              Create an account and confirm INR, timezone (Asia/Kolkata), and notification
              preferences.
            </p>
          </div>
          <div className="fs-card">
            <span>2</span>
            <h3>Bring Your Real Data</h3>
            <p>
              Add accounts, import CSV/XLSX statements, scan bill PDFs with OCR, or link read-only
              Gmail bill ingestion.
            </p>
          </div>
          <div className="fs-card">
            <span>3</span>
            <h3>Track, Forecast &amp; Ask AI</h3>
            <p>
              Monitor net position vs. upcoming commitments, manage reminders, and ask hybrid AI
              questions backed by citations.
            </p>
          </div>
        </div>
      </section>

      <section id="security" className="fs-section fs-center">
        <h2>Security you can verify</h2>
        <div className="fs-grid" style={{ textAlign: 'left' }}>
          <div className="fs-card">
            <h3>Session &amp; CSRF Protection</h3>
            <p>
              HttpOnly session cookies, Argon2id password hashing, and double-submit X-CSRF-Token
              validation on state-changing routes.
            </p>
          </div>
          <div className="fs-card">
            <h3>Multi-Tenant Isolation</h3>
            <p>
              Queries are scoped per authenticated user_id across ledgers, RAG document chunks, and
              chat histories.
            </p>
          </div>
          <div className="fs-card">
            <h3>No Unconsented Ledger Edits</h3>
            <p>
              Financial records, OCR extractions, and AI action drafts require explicit review unless
              you turn Auto-Execute Actions on.
            </p>
          </div>
          <div className="fs-card">
            <h3>Private Data Stays Private</h3>
            <p>
              Web search queries are sanitized so personal account names and exact bank balances are
              never sent to external search providers.
            </p>
          </div>
        </div>

        {/* Live Backend & Database Readiness Panel */}
        <div className="fs-status-panel">
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              marginBottom: '16px',
            }}
          >
            <div>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: '#a6ee62',
                  display: 'block',
                }}
              >
                System Foundation
              </span>
              <strong style={{ fontSize: '16px', fontWeight: 500, color: '#f1f7f2' }}>
                Live Backend &amp; PostgreSQL Readiness
              </strong>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              disabled={isLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                borderRadius: '999px',
                border: '1px solid rgba(190, 255, 200, 0.25)',
                background: 'rgba(8, 22, 14, 0.7)',
                color: '#f1f7f2',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              <RefreshCw
                style={{ width: '14px', height: '14px' }}
                className={isLoading ? 'animate-spin' : ''}
              />
              <span>Refresh</span>
            </button>
          </div>

          {error && !backendReachable && (
            <div
              role="alert"
              style={{
                marginBottom: '14px',
                padding: '12px 16px',
                borderRadius: '14px',
                border: '1px solid rgba(251, 113, 133, 0.45)',
                background: 'rgba(136, 19, 55, 0.35)',
                fontSize: '12px',
                color: '#ffe4e6',
              }}
            >
              <strong style={{ display: 'block' }}>Backend API Unreachable</strong>
              <span>The React frontend could not connect to FastAPI: {error}</span>
            </div>
          )}

          {backendReachable && readiness && !databaseReady && (
            <div
              role="alert"
              style={{
                marginBottom: '14px',
                padding: '12px 16px',
                borderRadius: '14px',
                border: '1px solid rgba(251, 191, 36, 0.45)',
                background: 'rgba(120, 53, 15, 0.35)',
                fontSize: '12px',
                color: '#fef3c7',
              }}
            >
              <strong style={{ display: 'block' }}>Database Degraded / Unreachable</strong>
              <span>
                FastAPI is responding, but the PostgreSQL readiness check failed:{' '}
                {readiness.database.error || 'Unknown error'}
              </span>
            </div>
          )}

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
              gap: '12px',
              fontSize: '12px',
            }}
          >
            <div
              style={{
                padding: '12px 14px',
                borderRadius: '14px',
                border: '1px solid rgba(190, 255, 200, 0.12)',
                background: 'rgba(255, 255, 255, 0.03)',
              }}
            >
              <span style={{ color: '#9db5a4', display: 'block' }}>FastAPI Service</span>
              <strong style={{ color: '#f1f7f2', fontWeight: 500 }}>
                {isLoading
                  ? 'Checking connection...'
                  : backendReachable
                  ? `Connected (${health?.version || 'live'})`
                  : 'Offline'}
              </strong>
            </div>

            <div
              style={{
                padding: '12px 14px',
                borderRadius: '14px',
                border: '1px solid rgba(190, 255, 200, 0.12)',
                background: 'rgba(255, 255, 255, 0.03)',
              }}
            >
              <span style={{ color: '#9db5a4', display: 'block' }}>PostgreSQL Engine</span>
              <strong style={{ color: '#f1f7f2', fontWeight: 500 }}>
                {isLoading
                  ? 'Checking readiness...'
                  : databaseReady
                  ? `Ready (${readiness?.database.latency_ms ?? 0} ms)`
                  : 'Disconnected'}
              </strong>
            </div>

            <div
              style={{
                padding: '12px 14px',
                borderRadius: '14px',
                border: '1px solid rgba(190, 255, 200, 0.12)',
                background: 'rgba(255, 255, 255, 0.03)',
              }}
            >
              <span style={{ color: '#9db5a4', display: 'block' }}>Primary Currency</span>
              <strong style={{ color: '#f1f7f2', fontWeight: 500 }}>
                {platform?.primary_currency === 'INR'
                  ? 'INR (Indian Rupee)'
                  : platform?.primary_currency || 'INR (Indian Rupee)'}
              </strong>
            </div>

            <div
              style={{
                padding: '12px 14px',
                borderRadius: '14px',
                border: '1px solid rgba(190, 255, 200, 0.12)',
                background: 'rgba(255, 255, 255, 0.03)',
              }}
            >
              <span style={{ color: '#9db5a4', display: 'block' }}>Fiscal Year Cycle</span>
              <strong style={{ color: '#f1f7f2', fontWeight: 500 }}>
                {platform?.fiscal_year_cycle === 'April - March'
                  ? 'April 1 – March 31'
                  : platform?.fiscal_year_cycle || 'April 1 – March 31'}
              </strong>
            </div>
          </div>
        </div>
      </section>

      <div className="fs-band">
        <div>
          <h2>Ready to organize every account, bill, EMI, and rupee in one place?</h2>
          <a
            className="fs-cta"
            href={isAuthenticated ? '/dashboard' : '/register'}
            onClick={handleRouteClick(isAuthenticated ? 'dashboard' : 'register')}
          >
            {isAuthenticated ? 'Go to Dashboard' : 'Create Account'} <b>→</b>
          </a>
        </div>
      </div>

      <footer className="fs-footer">
        {isAuthenticated ? (
          <>
            Signed in •{' '}
            <a href="/dashboard" onClick={handleRouteClick('dashboard')}>
              Open Dashboard
            </a>
          </>
        ) : (
          <>
            Already registered?{' '}
            <a href="/login" onClick={handleRouteClick('login')}>
              Sign In
            </a>
          </>
        )}
      </footer>
    </div>
  );
};
