import React, { useState } from 'react';
import { Mail, ArrowLeft, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authApi } from '../../services/authApi';
import { AuthFrame } from './AuthFrame';

interface ForgotPasswordPageProps {
  onNavigate: (view: string) => void;
}

export const ForgotPasswordPage: React.FC<ForgotPasswordPageProps> = ({ onNavigate }) => {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsLoading(true);

    try {
      await authApi.forgotPassword(email);
      setSubmitted(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to request password reset.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthFrame
      title="Reset Password"
      subtitle="Enter your email and we'll send a one-time password reset link."
      onNavigate={onNavigate}
      showLandingBack={false}
    >
      <button
        type="button"
        onClick={() => onNavigate('login')}
        className="inline-flex items-center space-x-1.5 text-xs text-slate-500 hover:text-indigo-600 mb-5 font-medium self-start"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to Sign In</span>
      </button>

      {submitted ? (
        <div className="p-5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs text-center space-y-2">
          <CheckCircle2 className="w-6 h-6 text-emerald-600 mx-auto" />
          <p className="font-semibold">Check your email</p>
          <p className="text-emerald-800 leading-relaxed">
            If an account is associated with that email, instructions to reset your password have
            been sent.
          </p>
        </div>
      ) : (
        <>
          {errorMessage && (
            <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.in"
                  required
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-xs font-semibold hover:from-indigo-700 hover:to-violet-700 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 shadow-sm"
            >
              <span>{isLoading ? 'Sending instructions...' : 'Send Reset Link'}</span>
              {!isLoading && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>
        </>
      )}
    </AuthFrame>
  );
};
