import React from 'react';

interface CardProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  headerAction?: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  children,
  className = '',
  headerAction,
}) => {
  return (
    <div
      className={`bg-white rounded-xl border border-slate-200/80 shadow-card hover:shadow-elevated/60 transition-shadow duration-200 overflow-hidden ${className}`}
    >
      {(title || headerAction) && (
        <div className="px-5 py-4 border-b border-slate-100/90 flex items-center justify-between gap-3">
          <div className="min-w-0">
            {title && <h3 className="text-sm font-semibold text-slate-900 truncate">{title}</h3>}
            {subtitle && <p className="text-xs text-slate-500 mt-0.5 truncate">{subtitle}</p>}
          </div>
          {headerAction && <div className="shrink-0">{headerAction}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
};
