import React, { useState } from 'react';
import { User, Mail, Shield, Calendar, Clock, CheckCircle2, AlertCircle, Save } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { authApi } from '../../services/authApi';

interface ProfilePageProps {
  onNavigate: (view: string) => void;
}

export const ProfilePage: React.FC<ProfilePageProps> = ({ onNavigate }) => {
  const { user, refreshUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [resendingEmail, setResendingEmail] = useState(false);
  const [emailMsg, setEmailMsg] = useState<string | null>(null);

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      setStatusMessage({ type: 'error', text: 'Full name cannot be empty.' });
      return;
    }

    setIsSaving(true);
    setStatusMessage(null);
    try {
      await authApi.updateProfile(fullName.trim());
      await refreshUser();
      setStatusMessage({ type: 'success', text: 'Profile updated successfully!' });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update profile.';
      setStatusMessage({ type: 'error', text: msg });
    } finally {
      setIsSaving(false);
    }
  };

  const handleResendVerification = async () => {
    if (!user?.email) return;
    setResendingEmail(true);
    setEmailMsg(null);
    try {
      const res = await authApi.resendVerification(user.email);
      setEmailMsg(res.message);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send verification email.';
      setEmailMsg(msg);
    } finally {
      setResendingEmail(false);
    }
  };

  if (!user) {
    return (
      <div className="p-8 text-center text-slate-500 text-xs">
        Please sign in to view your profile.
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">User Profile</h2>
        <p className="text-xs text-slate-500">
          Manage your personal account details and review your security credentials
        </p>
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

      {/* Account Info Cards */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-6">
        <form onSubmit={handleUpdate} className="space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Personal Details
          </h3>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Full Name
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                value={user.email}
                disabled
                className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 bg-slate-50 text-slate-500 rounded-lg cursor-not-allowed"
              />
            </div>
            <div className="flex items-center justify-between mt-1.5">
              <span className="text-[11px] text-slate-500">
                Email Status:{' '}
                {user.is_email_verified ? (
                  <span className="text-emerald-600 font-medium">Verified ✅</span>
                ) : (
                  <span className="text-amber-600 font-medium">Unverified ⚠️</span>
                )}
              </span>

              {!user.is_email_verified && (
                <button
                  type="button"
                  onClick={handleResendVerification}
                  disabled={resendingEmail}
                  className="text-[11px] text-emerald-600 hover:text-emerald-700 font-medium disabled:opacity-50"
                >
                  {resendingEmail ? 'Sending...' : 'Resend Verification Email'}
                </button>
              )}
            </div>
            {emailMsg && (
              <p className="text-[11px] text-slate-600 mt-1 bg-slate-50 p-2 rounded border border-slate-200">
                {emailMsg}
              </p>
            )}
          </div>

          <div className="pt-2 flex justify-end">
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors shadow-xs"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
            </button>
          </div>
        </form>

        <hr className="border-slate-100" />

        {/* Security & Metadata */}
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
            System & Security Metadata
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/60">
              <div className="flex items-center space-x-1.5 text-slate-500 mb-1">
                <Shield className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-[11px]">User Account ID (UUID)</span>
              </div>
              <div className="font-mono text-[10px] text-slate-700 break-all">{user.id}</div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/60">
              <div className="flex items-center space-x-1.5 text-slate-500 mb-1">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-[11px]">Account Created</span>
              </div>
              <div className="font-medium text-slate-700 text-xs">
                {new Date(user.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/60">
              <div className="flex items-center space-x-1.5 text-slate-500 mb-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-[11px]">Last Login</span>
              </div>
              <div className="font-medium text-slate-700 text-xs">
                {user.last_login_at
                  ? new Date(user.last_login_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
                  : 'Current Session'}
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/60">
              <div className="flex items-center space-x-1.5 text-slate-500 mb-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-[11px]">Onboarding Status</span>
              </div>
              <div className="font-medium text-slate-700 text-xs flex items-center justify-between">
                <span>{user.onboarding_completed ? 'Completed' : 'Pending / Skipped'}</span>
                {!user.onboarding_completed && (
                  <button
                    type="button"
                    onClick={() => onNavigate('onboarding')}
                    className="text-emerald-600 hover:text-emerald-700 text-[11px] underline"
                  >
                    Open Wizard
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
