import React, { useState } from 'react';
import { Eye, EyeOff, Lock, Mail, ArrowRight, AlertCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { AuthFrame } from './AuthFrame';

interface LoginPageProps {
  onNavigate: (view: string) => void;
  onSuccess?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onNavigate, onSuccess }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsLoading(true);

    try {
      await login(email, password);
      if (onSuccess) {
        onSuccess();
      } else {
        onNavigate('dashboard');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to sign in. Please check your credentials.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthFrame
      title="Sign in to your account"
      subtitle="India-First Personal Finance Manager • Secure Workspace"
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
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-xs font-semibold text-slate-700">Password</label>
            <button
              type="button"
              onClick={() => onNavigate('forgot-password')}
              className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
            >
              Forgot password?
            </button>
          </div>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full pl-10 pr-10 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-600 transition-colors"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3.5 top-2.5 text-slate-400 hover:text-slate-600"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500/30 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 shadow-sm"
        >
          <span>{isLoading ? 'Signing in...' : 'Sign In'}</span>
          {!isLoading && <ArrowRight className="w-4 h-4" />}
        </button>
      </form>

      <div className="mt-6 text-center">
        <p className="text-xs text-slate-500">
          Don&apos;t have an account?{' '}
          <button
            type="button"
            onClick={() => onNavigate('register')}
            className="font-semibold text-indigo-600 hover:text-indigo-700"
          >
            Create free account
          </button>
        </p>
      </div>
    </AuthFrame>
  );
};
