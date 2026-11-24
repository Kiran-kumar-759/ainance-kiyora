import React from 'react';

interface StatusIndicatorProps {
  status: 'online' | 'degraded' | 'offline' | 'loading';
  label: string;
  sublabel?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status, label, sublabel }) => {
  const dotColor = {
    online: 'bg-emerald-500',
    degraded: 'bg-amber-500',
    offline: 'bg-rose-500',
    loading: 'bg-slate-400 animate-pulse',
  }[status];

  const pingEffect = status === 'online' ? (
    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
  ) : null;

  return (
    <div className="flex items-center space-x-3">
      <div className="relative flex h-3 w-3">
        {pingEffect}
        <span className={`relative inline-flex rounded-full h-3 w-3 ${dotColor}`}></span>
      </div>
      <div>
        <div className="text-sm font-medium text-slate-800">{label}</div>
        {sublabel && <div className="text-xs text-slate-500">{sublabel}</div>}
      </div>
    </div>
  );
};
