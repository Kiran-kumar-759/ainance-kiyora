import React from 'react';

interface StatusIndicatorProps {
  label: string;
  status: 'online' | 'degraded' | 'offline' | 'loading';
  detail?: string;
}

const statusConfig = {
  online: {
    dot: 'bg-emerald-500',
    ping: 'bg-emerald-400',
    text: 'text-emerald-700',
    bg: 'bg-emerald-50/90 border-emerald-200/80',
  },
  degraded: {
    dot: 'bg-amber-500',
    ping: 'bg-amber-400',
    text: 'text-amber-800',
    bg: 'bg-amber-50/90 border-amber-200/80',
  },
  offline: {
    dot: 'bg-rose-500',
    ping: 'bg-rose-400',
    text: 'text-rose-700',
    bg: 'bg-rose-50/90 border-rose-200/80',
  },
  loading: {
    dot: 'bg-slate-400',
    ping: 'bg-slate-300',
    text: 'text-slate-600',
    bg: 'bg-slate-50/90 border-slate-200/80',
  },
};

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  label,
  status,
  detail,
}) => {
  const cfg = statusConfig[status];

  return (
    <div className={`flex items-center space-x-2.5 px-3 py-1.5 rounded-lg border ${cfg.bg}`}>
      <span className="relative flex h-2 w-2">
        {status === 'online' && (
          <span
            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${cfg.ping}`}
          />
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${cfg.dot}`} />
      </span>
      <div className="text-xs leading-none">
        <span className="font-medium text-slate-700">{label}: </span>
        <span className={`font-semibold ${cfg.text}`}>{detail || status}</span>
      </div>
    </div>
  );
};
