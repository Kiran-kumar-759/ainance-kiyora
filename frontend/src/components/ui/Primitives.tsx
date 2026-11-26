import React from 'react';
import { AlertTriangle, Loader2, RefreshCw, X } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'indigo';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
}

const BUTTON_VARIANTS: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary:
    'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm focus-visible:ring-indigo-500 border border-transparent',
  indigo:
    'bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white shadow-sm focus-visible:ring-indigo-500 border border-transparent',
  secondary:
    'bg-slate-900 hover:bg-slate-800 text-white shadow-sm focus-visible:ring-slate-700 border border-transparent',
  outline:
    'bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 hover:border-slate-300 shadow-card focus-visible:ring-indigo-500',
  ghost:
    'bg-transparent hover:bg-slate-100 text-slate-600 hover:text-slate-900 border border-transparent focus-visible:ring-indigo-500',
  danger:
    'bg-rose-600 hover:bg-rose-700 text-white shadow-sm focus-visible:ring-rose-500 border border-transparent',
};

const BUTTON_SIZES: Record<NonNullable<ButtonProps['size']>, string> = {
  xs: 'px-2.5 py-1 text-[11px] rounded-md gap-1',
  sm: 'px-3 py-1.5 text-xs rounded-lg gap-1.5',
  md: 'px-4 py-2 text-sm rounded-lg gap-2',
  lg: 'px-5 py-2.5 text-sm rounded-xl gap-2',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  ...rest
}) => (
  <button
    disabled={disabled || loading}
    className={`inline-flex items-center justify-center font-medium transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-55 disabled:cursor-not-allowed ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]} ${className}`}
    {...rest}
  >
    {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" /> : icon}
    {children}
  </button>
);

export const PageHeader: React.FC<{
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
}> = ({ title, subtitle, badge, actions }) => (
  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2.5">
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
        {badge}
      </div>
      {subtitle && <p className="text-xs sm:text-sm text-slate-500 leading-relaxed">{subtitle}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2.5 shrink-0">{actions}</div>}
  </div>
);

export const MetricCard: React.FC<{
  label: string;
  value: React.ReactNode;
  helper?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: 'default' | 'indigo' | 'emerald' | 'amber' | 'rose' | 'violet';
  highlight?: boolean;
}> = ({ label, value, helper, icon, tone = 'default', highlight = false }) => {
  const toneBorder: Record<NonNullable<typeof tone>, string> = {
    default: 'border-slate-200/80 bg-white',
    indigo: 'border-indigo-200/80 bg-gradient-to-br from-white to-indigo-50/45',
    emerald: 'border-emerald-200/80 bg-gradient-to-br from-white to-emerald-50/45',
    amber: 'border-amber-200/80 bg-gradient-to-br from-white to-amber-50/45',
    rose: 'border-rose-200/80 bg-gradient-to-br from-white to-rose-50/45',
    violet: 'border-violet-200/80 bg-gradient-to-br from-white to-violet-50/45',
  };

  return (
    <div
      className={`rounded-xl border p-4 sm:p-5 shadow-card transition-all duration-150 hover:shadow-elevated ${
        highlight ? 'glass-panel border-indigo-200/90' : toneBorder[tone]
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
          <p className="mt-1.5 text-xl sm:text-2xl font-bold tracking-tight text-slate-900 tabular-nums truncate">
            {value}
          </p>
        </div>
        {icon && (
          <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 text-indigo-600 shadow-xs shrink-0">
            {icon}
          </div>
        )}
      </div>
      {helper && <div className="mt-2.5 text-xs text-slate-500">{helper}</div>}
    </div>
  );
};

export const Skeleton: React.FC<{ className?: string }> = ({ className = 'h-4 w-full' }) => (
  <div className={`rounded-md skeleton-shimmer ${className}`} aria-hidden="true" />
);

export const SkeletonCard: React.FC<{ rows?: number }> = ({ rows = 3 }) => (
  <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card space-y-3" aria-hidden="true">
    <div className="flex items-center justify-between">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-6 w-16 rounded-full" />
    </div>
    {Array.from({ length: rows }).map((_, i) => (
      <Skeleton key={i} className={`h-3.5 ${i === rows - 1 ? 'w-2/3' : 'w-full'}`} />
    ))}
  </div>
);

export const EmptyState: React.FC<{
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}> = ({ icon, title, description, action }) => (
  <div className="rounded-xl border border-dashed border-slate-300 bg-white/80 px-6 py-10 text-center">
    {icon && (
      <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
        {icon}
      </div>
    )}
    <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
    <p className="mx-auto mt-1 max-w-md text-xs text-slate-500 leading-relaxed">{description}</p>
    {action && <div className="mt-4 flex justify-center">{action}</div>}
  </div>
);

export const ErrorBanner: React.FC<{
  title?: string;
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}> = ({ title = 'Unable to complete request', message, onRetry, onDismiss }) => (
  <div
    role="alert"
    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50/90 px-4 py-3 text-rose-900"
  >
    <div className="flex items-start gap-2.5">
      <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
      <div className="text-xs">
        <p className="font-semibold text-rose-900">{title}</p>
        <p className="text-rose-700 mt-0.5">{message}</p>
      </div>
    </div>
    <div className="flex items-center gap-2 shrink-0">
      {onRetry && (
        <Button variant="outline" size="xs" onClick={onRetry} icon={<RefreshCw className="w-3 h-3" />}>
          Retry
        </Button>
      )}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          className="text-rose-500 hover:text-rose-800 p-1 rounded"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  </div>
);

export const Modal: React.FC<{
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  maxWidthClass?: string;
}> = ({ open, onClose, title, subtitle, children, maxWidthClass = 'max-w-lg' }) => {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/55 backdrop-blur-xs animate-fadeIn"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={`w-full ${maxWidthClass} rounded-2xl border border-slate-200 bg-white shadow-glass overflow-hidden animate-slideUp`}
      >
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-slate-100 bg-slate-50/70">
          <div>
            <h3 className="text-base font-semibold text-slate-900">{title}</h3>
            {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-200/70 hover:text-slate-700 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 max-h-[82vh] overflow-y-auto">{children}</div>
      </div>
    </div>
  );
};
