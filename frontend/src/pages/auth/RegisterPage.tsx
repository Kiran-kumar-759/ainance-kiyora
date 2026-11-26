import React, { useState } from 'react';
import { Eye, EyeOff, Lock, Mail, User as UserIcon, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { AuthFrame } from './AuthFrame';

interface RegisterPageProps {
  onNavigate: (view: string) => void;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({ onNavigate }) => {
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [registeredSuccess, setRegisteredSuccess] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      await register(fullName, email, password);
      setRegisteredSuccess(email);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Registration failed. Please try again.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  if (registeredSuccess) {
    return (
      <AuthFrame
        title="Registration Complete"
        subtitle="Verify your email address to enable sensitive workspace operations"
        onNavigate={onNavigate}
        showLandingBack={false}
      >
        <div className="text-center py-4 space-y-4">
          <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            We have sent a verification email to{' '}
            <span className="font-semibold text-slate-900">{registeredSuccess}</span>. Please
            verify your email address to enable all sensitive account operations.
          </p>
          <button
            type="button"
            onClick={() => onNavigate('login')}
            className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-xs font-semibold hover:from-indigo-700 hover:to-violet-700 transition-all shadow-sm"
          >
            Proceed to Sign In
          </button>
        </div>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame
      title="Create your account"
      subtitle="India-First Personal Finance Manager • Private & Multi-User"
      onNavigate={onNavigate}
    >
      {errorMessage && (
        <div
          role="alert"
          className="mb-5 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2.5"
        >
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">Full Name</label>
          <div className="relative">
            <UserIcon className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Aarav Sharma"
              required
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600 transition-colors"
            />
          </div>
        </div>

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
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600 transition-colors"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">Password</label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 8 characters"
              required
              className="w-full pl-10 pr-10 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600 transition-colors"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="absolute right-3.5 top-2.5 text-slate-400 hover:text-slate-600"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Confirm Password
          </label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter password"
              required
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600 transition-colors"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500/30 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 shadow-sm mt-2"
        >
          <span>{isLoading ? 'Creating account...' : 'Create Account'}</span>
          {!isLoading && <ArrowRight className="w-4 h-4" />}
        </button>
      </form>

      <div className="mt-6 text-center">
        <p className="text-xs text-slate-500">
          Already have an account?{' '}
          <button
            type="button"
            onClick={() => onNavigate('login')}
            className="font-semibold text-indigo-600 hover:text-indigo-700"
          >
            Sign in
          </button>
        </p>
      </div>
    </AuthFrame>
  );
};
