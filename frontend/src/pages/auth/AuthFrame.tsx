import React from 'react';
import { ArrowLeft, CheckCircle2, Lock, ShieldCheck } from 'lucide-react';

interface AuthFrameProps {
  title: string;
  subtitle: string;
  onNavigate?: (view: string) => void;
  showLandingBack?: boolean;
  children: React.ReactNode;
}

export const AuthFrame: React.FC<AuthFrameProps> = ({
  title,
  subtitle,
  onNavigate,
  showLandingBack = true,
  children,
}) => (
  <div className="min-h-[85vh] flex items-center justify-center p-4 sm:p-6">
    <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-12 rounded-3xl overflow-hidden border border-slate-200/80 shadow-glass bg-white animate-slideUp">
      {/* Left Brand Story Panel (Desktop) */}
      <div className="hidden lg:flex lg:col-span-5 flex-col justify-between p-8 bg-navy-950 text-white relative overflow-hidden">
        <div
          aria-hidden="true"
          className="absolute -top-24 -left-16 w-64 h-64 rounded-full bg-indigo-600/25 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-24 -right-12 w-64 h-64 rounded-full bg-violet-600/20 blur-3xl"
        />

        <div className="relative space-y-6">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center font-bold text-lg shadow-sm">
              ₹
            </div>
            <div>
              <span className="text-sm font-bold block leading-tight">FinSight AI</span>
              <span className="text-[11px] text-indigo-300">India-First Finance</span>
            </div>
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold leading-snug text-white">
              Understand every rupee with clarity.
            </h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              Multi-account tracking, credit liability isolation, OCR receipts, and grounded AI
              guidance backed by PostgreSQL.
            </p>
          </div>

          <ul className="space-y-3 text-xs text-slate-200 pt-2">
            {[
              'INR formatting, April–March FY & IST dates',
              'Session cookies with CSRF & Argon2id protection',
              'Subscriptions, loans, bills & reminder logs',
            ].map((item) => (
              <li key={item} className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative pt-6 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-slate-400">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Multi-user strict isolation • Private workspace</span>
        </div>
      </div>

      {/* Right Form Panel */}
      <div className="lg:col-span-7 p-6 sm:p-10 flex flex-col justify-center">
        {showLandingBack && onNavigate && (
          <button
            type="button"
            onClick={() => onNavigate('foundation')}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-indigo-600 mb-5 self-start transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Overview</span>
          </button>
        )}

        <div className="mb-6">
          <div className="lg:hidden w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white font-bold text-lg flex items-center justify-center mb-3">
            ₹
          </div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h2>
          <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
        </div>

        {children}

        <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
          <Lock className="w-3 h-3" />
          <span>Encrypted transport & HttpOnly session cookies</span>
        </div>
      </div>
    </div>
  </div>
);
