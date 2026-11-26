import React, { useState } from 'react';
import { Lock, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authApi } from '../../services/authApi';
import { AuthFrame } from './AuthFrame';

interface ResetPasswordPageProps {
  token?: string;
  onNavigate: (view: string) => void;
}

export const ResetPasswordPage: React.FC<ResetPasswordPageProps> = ({
  token: propToken,
  onNavigate,
}) => {
  const [tokenInput, setTokenInput] = useState(propToken || '');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resetSuccess, setResetSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!tokenInput.trim()) {
      setErrorMessage('Reset token is required.');
      return;
    }

    if (newPassword.length < 8) {
      setErrorMessage('Password must be at least 8 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      await authApi.resetPassword(tokenInput.trim(), newPassword);
      setResetSuccess(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reset password.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  if (resetSuccess) {
    return (
      <AuthFrame
        title="Password Reset Complete"
        subtitle="All previous sessions have been revoked for security"
        onNavigate={onNavigate}
        showLandingBack={false}
      >
        <div className="text-center space-y-4 py-2">
          <CheckCircle2 className="w-12 h-12 text-emerald-600 mx-auto" />
          <p className="text-xs text-slate-600 leading-relaxed">
            Your password has been securely updated and all previous device sessions have been
            revoked. Please sign in with your new password.
          </p>
          <button
            type="button"
            onClick={() => onNavigate('login')}
            className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-xs font-semibold hover:from-indigo-700 hover:to-violet-700 transition-all shadow-sm"
          >
            Sign In Now
          </button>
        </div>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame
      title="Set New Password"
      subtitle="Enter your reset token and your new secure password."
      onNavigate={onNavigate}
    >
      {errorMessage && (
        <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {!propToken && (
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Reset Token
            </label>
            <input
              type="text"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="Paste token from email"
              required
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">New Password</label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Minimum 8 characters"
              required
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Confirm New Password
          </label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter password"
              required
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-xs font-semibold hover:from-indigo-700 hover:to-violet-700 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 shadow-sm"
        >
          <span>{isLoading ? 'Updating password...' : 'Update Password'}</span>
          {!isLoading && <ArrowRight className="w-4 h-4" />}
        </button>
      </form>
    </AuthFrame>
  );
};
