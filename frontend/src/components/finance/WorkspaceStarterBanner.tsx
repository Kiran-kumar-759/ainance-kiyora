import React from 'react';
import { FileSpreadsheet, Landmark, Sparkles, Wallet } from 'lucide-react';

interface WorkspaceStarterBannerProps {
  title: string;
  description: string;
  onNavigate: (view: string) => void;
  primaryAction?: {
    label: string;
    onClick: () => void;
  };
}

export const WorkspaceStarterBanner: React.FC<WorkspaceStarterBannerProps> = ({
  title,
  description,
  onNavigate,
  primaryAction,
}) => {
  return (
    <div className="rounded-2xl border border-indigo-200/80 bg-gradient-to-br from-white via-indigo-50/35 to-emerald-50/30 p-5 shadow-xs space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-bold text-slate-900">{title}</h3>
          <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{description}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {primaryAction && (
          <button
            type="button"
            onClick={primaryAction.onClick}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <span>{primaryAction.label}</span>
          </button>
        )}
        <button
          type="button"
          onClick={() => onNavigate('banking')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold transition-colors"
        >
          <Landmark className="w-3.5 h-3.5" />
          <span>Connect Bank Account</span>
        </button>
        <button
          type="button"
          onClick={() => onNavigate('accounts')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 text-xs font-semibold transition-colors"
        >
          <Wallet className="w-3.5 h-3.5 text-emerald-600" />
          <span>Add Account</span>
        </button>
        <button
          type="button"
          onClick={() => onNavigate('imports')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 text-xs font-semibold transition-colors"
        >
          <FileSpreadsheet className="w-3.5 h-3.5 text-purple-600" />
          <span>Import Statement</span>
        </button>
      </div>
    </div>
  );
};
