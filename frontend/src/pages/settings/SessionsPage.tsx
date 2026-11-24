import React, { useState, useEffect, useCallback } from 'react';
import { ShieldCheck, Monitor, Smartphone, Globe, Trash2, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authApi } from '../../services/authApi';
import { UserSession } from '../../types/auth';
import { useAuth } from '../../context/AuthContext';

interface SessionsPageProps {
  onNavigate?: (view: string) => void;
}

export const SessionsPage: React.FC<SessionsPageProps> = () => {
  const { logout } = useAuth();
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [isLoggingOutAll, setIsLoggingOutAll] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchSessions = useCallback(async () => {
    setIsLoading(true);
    setStatusMessage(null);
    try {
      const data = await authApi.listSessions();
      setSessions(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load active sessions.';
      setStatusMessage({ type: 'error', text: msg });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleRevoke = async (sessionId: string, isCurrent: boolean) => {
    if (isCurrent) {
      if (confirm('Revoking your current session will log you out immediately. Proceed?')) {
        await logout();
      }
      return;
    }

    setRevokingId(sessionId);
    setStatusMessage(null);
    try {
      const res = await authApi.revokeSession(sessionId);
      setStatusMessage({ type: 'success', text: res.message });
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to revoke session.';
      setStatusMessage({ type: 'error', text: msg });
    } finally {
      setRevokingId(null);
    }
  };

  const handleLogoutAll = async () => {
    if (!confirm('This will invalidate all your sessions across all devices (including this one). You will be logged out. Continue?')) {
      return;
    }

    setIsLoggingOutAll(true);
    try {
      await authApi.logoutAll();
      await logout();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to terminate all sessions.';
      setStatusMessage({ type: 'error', text: msg });
      setIsLoggingOutAll(false);
    }
  };

  const parseUserAgent = (ua: string | null) => {
    if (!ua) return { icon: Globe, label: 'Unknown Browser' };
    const lower = ua.toLowerCase();
    if (lower.includes('mobile') || lower.includes('android') || lower.includes('iphone')) {
      return { icon: Smartphone, label: 'Mobile Device' };
    }
    return { icon: Monitor, label: 'Desktop / Laptop' };
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Active Sessions & Security</h2>
          <p className="text-xs text-slate-500">
            Monitor and revoke active logins on your devices and web browsers
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={fetchSessions}
            disabled={isLoading}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition-colors shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-emerald-600' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            type="button"
            onClick={handleLogoutAll}
            disabled={isLoggingOutAll || sessions.length === 0}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-lg hover:bg-rose-100 disabled:opacity-50 transition-colors"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{isLoggingOutAll ? 'Terminating...' : 'Log Out All Devices'}</span>
          </button>
        </div>
      </div>

      {statusMessage && (
        <div
          className={`p-3 rounded-xl border text-xs flex items-center space-x-2 ${
            statusMessage.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-rose-50 text-rose-800 border-rose-200'
          }`}
        >
          {statusMessage.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          )}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* Sessions List */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs divide-y divide-slate-100">
        {isLoading && sessions.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin mx-auto mb-2" />
            Loading active sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            No active sessions found.
          </div>
        ) : (
          sessions.map((session) => {
            const { icon: DeviceIcon, label: deviceLabel } = parseUserAgent(session.user_agent);

            return (
              <div key={session.id} className="p-4 sm:p-5 flex items-start justify-between gap-4">
                <div className="flex items-start space-x-3.5">
                  <div className={`p-2.5 rounded-xl border ${session.is_current ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 'bg-slate-50 text-slate-500 border-slate-200'}`}>
                    <DeviceIcon className="w-5 h-5" />
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-semibold text-slate-900">{deviceLabel}</span>
                      {session.is_current && (
                        <span className="text-[10px] bg-emerald-100 text-emerald-800 font-medium px-2 py-0.5 rounded-full border border-emerald-200">
                          Current Session
                        </span>
                      )}
                    </div>

                    <div className="text-[11px] text-slate-500 font-mono">
                      IP: {session.ip_address || '127.0.0.1 (Localhost)'}
                    </div>

                    <div className="text-[11px] text-slate-400 truncate max-w-sm sm:max-w-md">
                      {session.user_agent || 'Unknown browser'}
                    </div>

                    <div className="text-[10px] text-slate-400 flex flex-wrap gap-x-4 pt-1">
                      <span>
                        Created: {new Date(session.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                      </span>
                      <span>
                        Last Active: {new Date(session.last_used_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                      </span>
                    </div>
                  </div>
                </div>

                <div>
                  <button
                    type="button"
                    onClick={() => handleRevoke(session.id, session.is_current)}
                    disabled={revokingId === session.id}
                    className={`inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      session.is_current
                        ? 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
                        : 'text-rose-600 hover:text-rose-800 hover:bg-rose-50'
                    }`}
                    title={session.is_current ? 'End current session' : 'Revoke device access'}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">
                      {revokingId === session.id ? 'Revoking...' : session.is_current ? 'Sign Out' : 'Revoke'}
                    </span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
