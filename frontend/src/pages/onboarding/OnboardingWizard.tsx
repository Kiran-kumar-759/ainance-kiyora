import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  User,
  Sliders,
  Bell,
  Check,
  FastForward,
} from 'lucide-react';
import { authApi } from '../../services/authApi';
import { useAuth } from '../../context/AuthContext';
import { UserPreferences } from '../../types/auth';

interface OnboardingWizardProps {
  onComplete: () => void;
}

export const OnboardingWizard: React.FC<OnboardingWizardProps> = ({ onComplete }) => {
  const { user, preferences, refreshUser } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Step 2 state: Profile
  const [fullName, setFullName] = useState(user?.full_name || '');

  // Step 3 state: Regional
  const [currency, setCurrency] = useState(preferences?.preferred_currency || 'INR');
  const [locale, setLocale] = useState(preferences?.locale || 'en-IN');
  const [timezone, setTimezone] = useState(preferences?.timezone || 'Asia/Kolkata');
  const [dateFormat, setDateFormat] = useState(preferences?.date_format || 'DD/MM/YYYY');

  // Step 4 state: Notifications
  const [emailAlerts, setEmailAlerts] = useState(preferences?.notification_preferences?.email_alerts ?? true);
  const [billReminders, setBillReminders] = useState(preferences?.notification_preferences?.bill_reminders ?? true);
  const [monthlySummary, setMonthlySummary] = useState(preferences?.notification_preferences?.monthly_summary ?? true);

  useEffect(() => {
    if (user?.full_name) setFullName(user.full_name);
    if (preferences) {
      setCurrency(preferences.preferred_currency || 'INR');
      setLocale(preferences.locale || 'en-IN');
      setTimezone(preferences.timezone || 'Asia/Kolkata');
      setDateFormat(preferences.date_format || 'DD/MM/YYYY');
      if (preferences.notification_preferences) {
        setEmailAlerts(preferences.notification_preferences.email_alerts ?? true);
        setBillReminders(preferences.notification_preferences.bill_reminders ?? true);
        setMonthlySummary(preferences.notification_preferences.monthly_summary ?? true);
      }
    }
  }, [user, preferences]);

  const saveCurrentStepData = async () => {
    const patchData: Partial<UserPreferences> & { full_name?: string } = {
      full_name: fullName,
      preferred_currency: currency,
      locale,
      timezone,
      date_format: dateFormat,
      notification_preferences: {
        email_alerts: emailAlerts,
        bill_reminders: billReminders,
        monthly_summary: monthlySummary,
      },
    };
    await authApi.updateOnboarding(patchData);
  };

  const handleNext = async () => {
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      await saveCurrentStepData();
      if (currentStep < 5) {
        setCurrentStep((prev) => prev + 1);
      } else {
        await handleComplete();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save onboarding progress.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleSkip = async () => {
    setIsSubmitting(true);
    try {
      await authApi.skipOnboarding();
      await refreshUser();
      onComplete();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to skip onboarding.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleComplete = async () => {
    setIsSubmitting(true);
    try {
      await authApi.completeOnboarding();
      await refreshUser();
      onComplete();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to complete onboarding.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const steps = [
    { num: 1, title: 'Welcome', icon: Sparkles },
    { num: 2, title: 'Profile', icon: User },
    { num: 3, title: 'Regional', icon: Sliders },
    { num: 4, title: 'Alerts', icon: Bell },
    { num: 5, title: 'Ready', icon: CheckCircle2 },
  ];

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      {/* Wizard Progress Stepper */}
      <div className="mb-8">
        <div className="flex items-center justify-between relative">
          <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-slate-200 -translate-y-1/2 z-0" />
          <div
            className="absolute top-1/2 left-0 h-0.5 bg-emerald-500 -translate-y-1/2 z-0 transition-all duration-300"
            style={{ width: `${((currentStep - 1) / (steps.length - 1)) * 100}%` }}
          />

          {steps.map((s) => {
            const Icon = s.icon;
            const isDone = s.num < currentStep;
            const isCurrent = s.num === currentStep;

            return (
              <div key={s.num} className="relative z-10 flex flex-col items-center">
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-colors ${
                    isDone
                      ? 'bg-emerald-600 border-emerald-600 text-white'
                      : isCurrent
                      ? 'bg-white border-emerald-600 text-emerald-600 shadow-sm'
                      : 'bg-white border-slate-300 text-slate-400'
                  }`}
                >
                  {isDone ? <Check className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                </div>
                <span
                  className={`text-[11px] font-medium mt-1.5 hidden sm:block ${
                    isCurrent ? 'text-emerald-700 font-semibold' : 'text-slate-500'
                  }`}
                >
                  {s.title}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
        {errorMessage && (
          <div className="mb-6 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-lg">
            {errorMessage}
          </div>
        )}

        {/* Step 1: Welcome */}
        {currentStep === 1 && (
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 font-bold text-2xl flex items-center justify-center mb-2">
              ₹
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Welcome to AI Personal Finance Manager
            </h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              Designed specifically for individuals in India. We help you track bank accounts,
              categorize transactions, manage recurring bills, monitor loans and EMIs, and build financial
              wealth with AI intelligence.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4">
              <div className="p-3 bg-slate-50 border border-slate-200/70 rounded-xl text-xs">
                <div className="font-semibold text-slate-800 mb-1">🇮🇳 India-First Architecture</div>
                <p className="text-slate-500 text-[11px]">
                  Built for Indian Rupee (INR), Lakhs/Crores grouping, and April–March Financial Years.
                </p>
              </div>
              <div className="p-3 bg-slate-50 border border-slate-200/70 rounded-xl text-xs">
                <div className="font-semibold text-slate-800 mb-1">🔒 Private & Isolated</div>
                <p className="text-slate-500 text-[11px]">
                  Strict multi-user row-level isolation and zero phantom or fabricated data.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Profile */}
        {currentStep === 2 && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Confirm Your Profile</h2>
            <p className="text-xs text-slate-500">
              Personalize your account details for accurate communication and reporting.
            </p>
            <div className="space-y-3 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                  placeholder="e.g. Rahul Sharma"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Email Address</label>
                <input
                  type="email"
                  value={user?.email || ''}
                  disabled
                  className="w-full px-3 py-2 text-xs border border-slate-200 bg-slate-50 text-slate-500 rounded-lg cursor-not-allowed"
                />
                <span className="text-[10px] text-slate-400 mt-1 block">
                  Email verification status: {user?.is_email_verified ? 'Verified ✅' : 'Unverified (check your inbox)'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Regional */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Regional Preferences</h2>
            <p className="text-xs text-slate-500">
              Configure currency, formatting, and Indian timezone standards.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Currency</label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  <option value="INR">INR (₹) - Indian Rupee</option>
                  <option value="USD">USD ($) - US Dollar</option>
                  <option value="EUR">EUR (€) - Euro</option>
                  <option value="GBP">GBP (£) - British Pound</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Locale & Number Format</label>
                <select
                  value={locale}
                  onChange={(e) => setLocale(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  <option value="en-IN">English (India) - ₹1,00,000.00</option>
                  <option value="en-US">English (US) - $100,000.00</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Timezone</label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  <option value="Asia/Kolkata">Asia/Kolkata (IST +05:30)</option>
                  <option value="UTC">UTC (+00:00)</option>
                  <option value="America/New_York">America/New_York (EST)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Date Format</label>
                <select
                  value={dateFormat}
                  onChange={(e) => setDateFormat(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  <option value="DD/MM/YYYY">DD/MM/YYYY (Standard India)</option>
                  <option value="YYYY-MM-DD">YYYY-MM-DD (ISO)</option>
                  <option value="MM/DD/YYYY">MM/DD/YYYY (US)</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Notifications */}
        {currentStep === 4 && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Notifications & Alerts</h2>
            <p className="text-xs text-slate-500">
              Choose how you want to be notified about important financial events.
            </p>
            <div className="space-y-3 pt-2">
              <label className="flex items-center justify-between p-3 border border-slate-200 rounded-xl hover:bg-slate-50 cursor-pointer">
                <div>
                  <div className="text-xs font-semibold text-slate-800">Security & Email Alerts</div>
                  <div className="text-[11px] text-slate-500">Login alerts, password changes, and security updates</div>
                </div>
                <input
                  type="checkbox"
                  checked={emailAlerts}
                  onChange={(e) => setEmailAlerts(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
              </label>

              <label className="flex items-center justify-between p-3 border border-slate-200 rounded-xl hover:bg-slate-50 cursor-pointer">
                <div>
                  <div className="text-xs font-semibold text-slate-800">Bill & EMI Reminders</div>
                  <div className="text-[11px] text-slate-500">Upcoming bill deadlines and EMI debit notifications</div>
                </div>
                <input
                  type="checkbox"
                  checked={billReminders}
                  onChange={(e) => setBillReminders(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
              </label>

              <label className="flex items-center justify-between p-3 border border-slate-200 rounded-xl hover:bg-slate-50 cursor-pointer">
                <div>
                  <div className="text-xs font-semibold text-slate-800">Monthly Spending Summary</div>
                  <div className="text-[11px] text-slate-500">Monthly breakdown and AI financial insights report</div>
                </div>
                <input
                  type="checkbox"
                  checked={monthlySummary}
                  onChange={(e) => setMonthlySummary(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
              </label>
            </div>
          </div>
        )}

        {/* Step 5: Ready */}
        {currentStep === 5 && (
          <div className="text-center space-y-4 py-2">
            <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">You're All Set!</h2>
            <p className="text-xs text-slate-600 max-w-md mx-auto">
              Your profile and preferences have been customized. You are now ready to use the platform.
            </p>
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-left text-xs max-w-md mx-auto space-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-500">Name:</span>
                <span className="font-medium text-slate-800">{fullName || 'User'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Currency:</span>
                <span className="font-medium text-slate-800">{currency}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Timezone:</span>
                <span className="font-medium text-slate-800">{timezone}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Format:</span>
                <span className="font-medium text-slate-800">{dateFormat}</span>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-8 pt-4 border-t border-slate-200/80 flex items-center justify-between">
          <div>
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={handleBack}
                disabled={isSubmitting}
                className="inline-flex items-center space-x-1 px-3 py-2 text-xs font-medium text-slate-600 hover:text-slate-900"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSkip}
                disabled={isSubmitting}
                className="inline-flex items-center space-x-1 px-3 py-2 text-xs font-medium text-slate-500 hover:text-slate-800"
              >
                <FastForward className="w-3.5 h-3.5" />
                <span>Skip for now</span>
              </button>
            )}
          </div>

          <div className="flex items-center space-x-3">
            {currentStep > 1 && currentStep < 5 && (
              <button
                type="button"
                onClick={handleSkip}
                disabled={isSubmitting}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                Skip wizard
              </button>
            )}
            <button
              type="button"
              onClick={handleNext}
              disabled={isSubmitting}
              className="inline-flex items-center space-x-1.5 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors shadow-sm"
            >
              <span>{currentStep === 5 ? 'Get Started' : 'Continue'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
