import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'success' | 'warning' | 'danger' | 'neutral' | 'info' | 'violet';
  className?: string;
}

const variantClasses: Record<NonNullable<BadgeProps['variant']>, string> = {
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200/90',
  warning: 'bg-amber-50 text-amber-800 border-amber-200/90',
  danger: 'bg-rose-50 text-rose-700 border-rose-200/90',
  neutral: 'bg-slate-100 text-slate-700 border-slate-200/90',
  info: 'bg-indigo-50 text-indigo-700 border-indigo-200/90',
  violet: 'bg-violet-50 text-violet-700 border-violet-200/90',
};

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  className = '',
}) => {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
};
