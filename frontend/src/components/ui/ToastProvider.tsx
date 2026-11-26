import React, { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastTone = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface ToastContextValue {
  pushToast: (toast: Omit<ToastItem, 'id'>, durationMs?: number) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    (toast: Omit<ToastItem, 'id'>, durationMs: number = 4200) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setToasts((prev) => [...prev.slice(-4), { ...toast, id }]);
      if (durationMs > 0) {
        window.setTimeout(() => {
          setToasts((prev) => prev.filter((item) => item.id !== id));
        }, durationMs);
      }
    },
    []
  );

  const toneConfig: Record<ToastTone, { icon: React.ReactNode; classes: string }> = {
    success: {
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />,
      classes: 'border-emerald-200 bg-white/95 text-slate-900',
    },
    error: {
      icon: <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />,
      classes: 'border-rose-200 bg-white/95 text-slate-900',
    },
    warning: {
      icon: <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />,
      classes: 'border-amber-200 bg-white/95 text-slate-900',
    },
    info: {
      icon: <Info className="w-4 h-4 text-indigo-600 shrink-0" />,
      classes: 'border-indigo-200 bg-white/95 text-slate-900',
    },
  };

  return (
    <ToastContext.Provider value={{ pushToast, dismissToast }}>
      {children}
      <div
        aria-live="polite"
        aria-label="Notifications"
        className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-sm w-full pointer-events-none px-4 sm:px-0"
      >
        {toasts.map((toast) => {
          const cfg = toneConfig[toast.tone];
          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex items-start gap-2.5 rounded-xl border px-3.5 py-3 shadow-elevated backdrop-blur-md animate-slideUp ${cfg.classes}`}
              role="status"
            >
              <div className="mt-0.5">{cfg.icon}</div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-slate-900">{toast.title}</p>
                {toast.description && (
                  <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">{toast.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismissToast(toast.id)}
                aria-label="Dismiss notification"
                className="text-slate-400 hover:text-slate-700 p-0.5 rounded transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return {
      pushToast: () => {},
      dismissToast: () => {},
    };
  }
  return ctx;
}
