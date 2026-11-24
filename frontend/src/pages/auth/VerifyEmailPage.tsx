import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle2, AlertCircle, RefreshCw, Mail, ArrowRight } from 'lucide-react';
import { authApi } from '../../services/authApi';
import { useAuth } from '../../context/AuthContext';

interface VerifyEmailPageProps {
  token?: string;
  onNavigate: (view: string) => void;
}

export const VerifyEmailPage: React.FC<VerifyEmailPageProps> = ({ token: initialToken, onNavigate }) => {
  const { user, refreshUser } = useAuth();
  const [token, setToken] = useState<string>(initialToken || '');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string>('');
  const [resendEmail, setResendEmail] = useState<string>(user?.email || '');
  const [resendStatus, setResendStatus] = useState<string | null>(null);
  const [isResending, setIsResending] = useState<boolean>(false);

  const handleVerify = useCallback(async (tokenToVerify: string) => {
    if (!tokenToVerify.trim()) {
      setStatus('error');
      setMessage('Verification token cannot be empty.');
      return;
    }

    setStatus('loading');
    setMessage('');
    try {
      const res = await authApi.verifyEmail(tokenToVerify.trim());
      setStatus('success');
      setMessage(res.message || 'Email verified successfully! Your account is now fully verified.');
      await refreshUser();
    } catch (err: unknown) {
      setStatus('error');
      const errorText = err instanceof Error ? err.message : 'Invalid or expired verification token.';
      setMessage(errorText);
    }
  }, [refreshUser]);

  useEffect(() => {
    if (initialToken) {
      handleVerify(initialToken);
    }
  }, [initialToken, handleVerify]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resendEmail.trim()) {
      setResendStatus('Please enter an email address.');
      return;
    }

    setIsResending(true);
    setResendStatus(null);
    try {
      const res = await authApi.resendVerification(resendEmail.trim());
      setResendStatus(res.message);
    } catch (err: unknown) {
      const errorText = err instanceof Error ? err.message : 'Failed to resend verification email.';
      setResendStatus(errorText);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200/80 shadow-sm p-8">
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 flex items-center justify-center mx-auto mb-3">
            <Mail className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Verify Your Email</h2>
          <p className="text-xs text-slate-500 mt-1">
            Confirm your email address to unlock full features on the platform
          </p>
        </div>

        {status === 'loading' && (
          <div className="text-center py-6">
            <RefreshCw className="w-8 h-8 text-emerald-600 animate-spin mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-700">Verifying your token with the server...</p>
          </div>
        )}

        {status === 'success' && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center mb-6">
            <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-emerald-900">Email Verified!</h3>
            <p className="text-xs text-emerald-700 mt-1">{message}</p>
            <div className="mt-4">
              <button
                type="button"
                onClick={() => onNavigate(user ? 'foundation' : 'login')}
                className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-medium transition-colors"
              >
                <span>{user ? 'Continue to App' : 'Proceed to Sign In'}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {status === 'error' && (
          <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 mb-6">
            <div className="flex items-start space-x-2.5">
              <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-semibold text-rose-900">Verification Failed</h4>
                <p className="text-xs text-rose-700 mt-0.5">{message}</p>
              </div>
            </div>
          </div>
        )}

        {status !== 'success' && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleVerify(token);
            }}
            className="space-y-4 mb-6"
          >
            <div>
              <label htmlFor="token" className="block text-xs font-medium text-slate-700 mb-1">
                Verification Token
              </label>
              <input
                id="token"
                type="text"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste the token from your email"
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={status === 'loading' || !token.trim()}
              className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5"
            >
              <span>Verify Token</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>
        )}

        <hr className="border-slate-200/80 my-6" />

        {/* Resend Verification Section */}
        <div className="bg-slate-50 border border-slate-200/60 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-slate-800 mb-1">Need a new verification link?</h4>
          <p className="text-[11px] text-slate-500 mb-3">
            Tokens expire in 24 hours. Enter your email below to receive a new one.
          </p>

          {resendStatus && (
            <div className="mb-3 p-2.5 bg-white border border-slate-200 rounded text-xs text-slate-700">
              {resendStatus}
            </div>
          )}

          <form onSubmit={handleResend} className="flex gap-2">
            <input
              type="email"
              value={resendEmail}
              onChange={(e) => setResendEmail(e.target.value)}
              placeholder="user@example.com"
              required
              className="flex-1 px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
            />
            <button
              type="submit"
              disabled={isResending}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
            >
              {isResending ? 'Sending...' : 'Resend'}
            </button>
          </form>
        </div>

        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={() => onNavigate(user ? 'foundation' : 'login')}
            className="text-xs text-slate-500 hover:text-slate-800 transition-colors"
          >
            ← Back to {user ? 'Dashboard' : 'Sign In'}
          </button>
        </div>
      </div>
    </div>
  );
};
