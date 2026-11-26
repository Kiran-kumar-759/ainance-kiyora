import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Bell,
  Bot,
  CheckCircle2,
  Database,
  Download,
  Globe,
  KeyRound,
  Layout,
  Lock,
  Monitor,
  Plug,
  RefreshCw,
  Save,
  Settings,
  Shield,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Trash2,
  User as UserIcon,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { config } from '../../lib/config';
import { assistantApi } from '../../services/assistantApi';
import { authApi } from '../../services/authApi';
import { integrationsApi } from '../../services/integrationsApi';
import { UserAiPreference, WebProviderId, WebProviderStatus } from '../../types/assistant';
import { PrivacyDataSummary, UserSession } from '../../types/auth';
import { IntegrationItem } from '../../types/integrations';

interface SettingsPageProps {
  onNavigate: (view: string) => void;
}

type SettingsTabId =
  | 'profile'
  | 'security'
  | 'localization'
  | 'notifications'
  | 'ai'
  | 'privacy'
  | 'application';

const SETTINGS_TABS: { id: SettingsTabId; label: string; icon: React.ElementType }[] = [
  { id: 'profile', label: 'Profile & Account', icon: UserIcon },
  { id: 'security', label: 'Security & Sessions', icon: ShieldCheck },
  { id: 'localization', label: 'Localization', icon: Globe },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'ai', label: 'AI Assistant', icon: Bot },
  { id: 'privacy', label: 'Privacy & Data', icon: Database },
  { id: 'application', label: 'Application', icon: Layout },
];

export const SettingsPage: React.FC<SettingsPageProps> = ({ onNavigate }) => {
  const { user, preferences, refreshUser, updatePreferences, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<SettingsTabId>('profile');
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(
    null
  );

  // 1. Profile state
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [savingProfile, setSavingProfile] = useState(false);
  const [resendingVerification, setResendingVerification] = useState(false);

  // 2. Security & Sessions state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [revokeOtherSessions, setRevokeOtherSessions] = useState(true);
  const [changingPassword, setChangingPassword] = useState(false);
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [confirmSessionAction, setConfirmSessionAction] = useState<
    { type: 'single'; session: UserSession } | { type: 'all' } | null
  >(null);

  // 3 & 4 & 7. UserPreferences fields
  const [currency, setCurrency] = useState(preferences?.preferred_currency || 'INR');
  const [locale, setLocale] = useState(preferences?.locale || 'en-IN');
  const [timezone, setTimezone] = useState(preferences?.timezone || 'Asia/Kolkata');
  const [dateFormat, setDateFormat] = useState(preferences?.date_format || 'DD/MM/YYYY');
  const [weekStart, setWeekStart] = useState<'monday' | 'sunday'>(
    (preferences?.notification_preferences?.week_start as 'monday' | 'sunday') || 'monday'
  );
  const [language, setLanguage] = useState<string>(
    String(preferences?.notification_preferences?.language || 'en-IN')
  );

  const [billReminders, setBillReminders] = useState(true);
  const [subscriptionReminders, setSubscriptionReminders] = useState(true);
  const [loanEmiReminders, setLoanEmiReminders] = useState(true);
  const [paymentDueReminders, setPaymentDueReminders] = useState(true);
  const [financialInsights, setFinancialInsights] = useState(true);
  const [spendingAnomalies, setSpendingAnomalies] = useState(true);
  const [forecastNotifications, setForecastNotifications] = useState(true);
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [emailRemindersEnabled, setEmailRemindersEnabled] = useState(true);
  const [smsRemindersEnabled, setSmsRemindersEnabled] = useState(false);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [monthlySummary, setMonthlySummary] = useState(true);

  const [defaultLandingView, setDefaultLandingView] = useState<
    'dashboard' | 'analytics' | 'assistant' | 'bills' | 'transactions'
  >('dashboard');
  const [compactSidebar, setCompactSidebar] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [smtpItem, setSmtpItem] = useState<IntegrationItem | null>(null);

  // 5. AI Assistant Preferences state
  const [aiPrefs, setAiPrefs] = useState<UserAiPreference | null>(null);
  const [webProviders, setWebProviders] = useState<WebProviderStatus[]>([]);
  const [groqInfo, setGroqInfo] = useState<IntegrationItem | null>(null);
  const [savingAiPrefs, setSavingAiPrefs] = useState(false);

  // 6. Privacy summary state
  const [privacySummary, setPrivacySummary] = useState<PrivacyDataSummary | null>(null);
  const [loadingPrivacy, setLoadingPrivacy] = useState(false);

  // Sync local form fields when preferences load/refresh
  const syncPrefsFromContext = useCallback(() => {
    if (!preferences) return;
    setCurrency(preferences.preferred_currency || 'INR');
    setLocale(preferences.locale || 'en-IN');
    setTimezone(preferences.timezone || 'Asia/Kolkata');
    setDateFormat(preferences.date_format || 'DD/MM/YYYY');
    const np = preferences.notification_preferences || {};
    setWeekStart((np.week_start as 'monday' | 'sunday') || 'monday');
    setLanguage(String(np.language || 'en-IN'));
    setBillReminders(np.bill_reminders ?? true);
    setSubscriptionReminders(np.subscription_reminders ?? true);
    setLoanEmiReminders(np.loan_emi_reminders ?? true);
    setPaymentDueReminders(np.payment_due_reminders ?? true);
    setFinancialInsights(np.financial_insights ?? true);
    setSpendingAnomalies(np.spending_anomalies ?? true);
    setForecastNotifications(np.forecast_notifications ?? true);
    setEmailAlerts(np.email_alerts ?? true);
    setEmailRemindersEnabled(np.email_reminders_enabled ?? true);
    setSmsRemindersEnabled(np.sms_reminders_enabled ?? false);
    setPhoneNumber(String(np.phone_number || ''));
    setMonthlySummary(np.monthly_summary ?? true);
    setDefaultLandingView(
      (np.default_landing_view as 'dashboard' | 'analytics' | 'assistant' | 'bills' | 'transactions') ||
        'dashboard'
    );
    setCompactSidebar(Boolean(np.compact_sidebar ?? false));
  }, [preferences]);

  useEffect(() => {
    setFullName(user?.full_name || '');
  }, [user]);

  useEffect(() => {
    syncPrefsFromContext();
  }, [syncPrefsFromContext]);

  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const list = await authApi.listSessions();
      setSessions(list);
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Unable to load active sessions.',
      });
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  const loadAiAndIntegrations = useCallback(async () => {
    try {
      const [prefRes, providersRes, overviewRes] = await Promise.all([
        assistantApi.getPreferences(),
        assistantApi.listProviders(),
        integrationsApi.getOverview().catch(() => null),
      ]);
      setAiPrefs(prefRes);
      setWebProviders(providersRes);
      if (overviewRes) {
        setSmtpItem(overviewRes.integrations.find((i) => i.provider_id === 'smtp') || null);
        setGroqInfo(overviewRes.integrations.find((i) => i.provider_id === 'groq') || null);
      }
    } catch {
      // Non-fatal while switching tabs
    }
  }, []);

  const loadPrivacy = useCallback(async () => {
    setLoadingPrivacy(true);
    try {
      const res = await authApi.getPrivacySummary();
      setPrivacySummary(res);
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Unable to load privacy summary.',
      });
    } finally {
      setLoadingPrivacy(false);
    }
  }, []);

  useEffect(() => {
    setStatusMessage(null);
    if (activeTab === 'security') void loadSessions();
    if (activeTab === 'ai' || activeTab === 'notifications') void loadAiAndIntegrations();
    if (activeTab === 'privacy') void loadPrivacy();
  }, [activeTab, loadSessions, loadAiAndIntegrations, loadPrivacy]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (fullName.trim().length < 2) {
      setStatusMessage({ type: 'error', text: 'Full name must be at least 2 characters.' });
      return;
    }
    setSavingProfile(true);
    setStatusMessage(null);
    try {
      await authApi.updateProfile(fullName.trim());
      await refreshUser();
      setStatusMessage({ type: 'success', text: 'Profile details updated in PostgreSQL.' });
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to update profile.',
      });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleResendVerification = async () => {
    if (!user?.email) return;
    setResendingVerification(true);
    setStatusMessage(null);
    try {
      const res = await authApi.resendVerification(user.email);
      setStatusMessage({ type: 'success', text: res.message });
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to send verification email.',
      });
    } finally {
      setResendingVerification(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);
    if (newPassword.length < 8) {
      setStatusMessage({ type: 'error', text: 'New password must be at least 8 characters long.' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setStatusMessage({ type: 'error', text: 'New password and confirmation do not match.' });
      return;
    }
    setChangingPassword(true);
    try {
      const res = await authApi.changePassword(currentPassword, newPassword, revokeOtherSessions);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setStatusMessage({ type: 'success', text: res.message });
      await loadSessions();
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Password change failed.',
      });
    } finally {
      setChangingPassword(false);
    }
  };

  const handleConfirmSessionAction = async () => {
    if (!confirmSessionAction) return;
    setStatusMessage(null);
    try {
      if (confirmSessionAction.type === 'all') {
        await authApi.logoutAll();
        await logout();
        onNavigate('login');
      } else {
        const s = confirmSessionAction.session;
        if (s.is_current) {
          await logout();
          onNavigate('login');
        } else {
          const res = await authApi.revokeSession(s.id);
          setSessions((prev) => prev.filter((item) => item.id !== s.id));
          setStatusMessage({ type: 'success', text: res.message });
        }
      }
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Session action failed.',
      });
    } finally {
      setConfirmSessionAction(null);
    }
  };

  const handleSaveUserPreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingPrefs(true);
    setStatusMessage(null);
    try {
      await updatePreferences({
        preferred_currency: currency,
        locale,
        timezone,
        date_format: dateFormat,
        notification_preferences: {
          bill_reminders: billReminders,
          subscription_reminders: subscriptionReminders,
          loan_emi_reminders: loanEmiReminders,
          payment_due_reminders: paymentDueReminders,
          financial_insights: financialInsights,
          spending_anomalies: spendingAnomalies,
          forecast_notifications: forecastNotifications,
          email_alerts: emailAlerts,
          email_reminders_enabled: emailRemindersEnabled,
          sms_reminders_enabled: smsRemindersEnabled,
          phone_number: phoneNumber.trim() || undefined,
          monthly_summary: monthlySummary,
          number_format: locale,
          week_start: weekStart,
          language,
          default_landing_view: defaultLandingView,
          compact_sidebar: compactSidebar,
        },
      });
      setStatusMessage({ type: 'success', text: 'Preferences saved cleanly to PostgreSQL.' });
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to save preferences.',
      });
    } finally {
      setSavingPrefs(false);
    }
  };

  const handleSaveAiPreferences = async (patch: Partial<UserAiPreference>) => {
    setSavingAiPrefs(true);
    setStatusMessage(null);
    try {
      const updated = await assistantApi.updatePreferences(patch);
      setAiPrefs(updated);
      setStatusMessage({
        type: 'success',
        text: 'AI Assistant & Web Research preferences updated.',
      });
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to update AI preferences.',
      });
    } finally {
      setSavingAiPrefs(false);
    }
  };

  const handleExportCsv = (endpoint: string) => {
    if (typeof window !== 'undefined') {
      window.open(`${config.apiBaseUrl}${endpoint}`, '_blank', 'noopener,noreferrer');
    }
  };

  if (!user) {
    return (
      <div className="p-8 text-center text-xs text-slate-500">
        Please sign in to manage account settings.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
            <Settings className="w-5 h-5 text-indigo-600" />
            <span>Settings Center</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage your profile, password & active sessions, Indian localization, reminder channels, AI preferences, privacy disclosures, and workspace defaults.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 self-start">
          <button
            type="button"
            onClick={() => onNavigate('reminders')}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
          >
            <Bell className="w-3.5 h-3.5" />
            <span>Reminders &amp; Channels</span>
          </button>
          <button
            type="button"
            onClick={() => onNavigate('integrations')}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
          >
            <Plug className="w-3.5 h-3.5" />
            <span>Integrations</span>
          </button>
        </div>
      </div>

      {statusMessage && (
        <div
          role="status"
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

      <div className="flex flex-col md:flex-row gap-6">
        {/* Settings Section Navigation */}
        <nav
          aria-label="Settings sections"
          role="tablist"
          className="md:w-60 flex-shrink-0 flex md:flex-col gap-1.5 overflow-x-auto pb-1 md:pb-0"
        >
          {SETTINGS_TABS.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors ${
                  active
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-white border border-slate-200/80 text-slate-600 hover:bg-slate-50'
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? 'text-emerald-400' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Main Panel Content */}
        <div className="flex-1 min-w-0 space-y-6">
          {/* 1. PROFILE & ACCOUNT */}
          {activeTab === 'profile' && (
            <form
              onSubmit={(e) => void handleSaveProfile(e)}
              className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-5"
            >
              <div className="border-b border-slate-100 pb-3">
                <h3 className="text-sm font-semibold text-slate-900">Profile & Account</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Update your display name and verify your registered account identity.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="settings-full-name" className="block text-xs font-medium text-slate-700 mb-1">
                    Display Name
                  </label>
                  <input
                    id="settings-full-name"
                    type="text"
                    required
                    minLength={2}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label htmlFor="settings-email" className="block text-xs font-medium text-slate-700 mb-1">
                    Email Address
                  </label>
                  <input
                    id="settings-email"
                    type="email"
                    disabled
                    value={user.email}
                    className="w-full px-3 py-2 text-xs border border-slate-200 bg-slate-50 text-slate-500 rounded-lg cursor-not-allowed"
                  />
                  <div className="mt-1.5 flex items-center justify-between text-[11px]">
                    <span className={user.is_email_verified ? 'text-emerald-600 font-medium' : 'text-amber-600 font-medium'}>
                      {user.is_email_verified ? 'Verified email' : 'Email verification pending'}
                    </span>
                    {!user.is_email_verified && (
                      <button
                        type="button"
                        disabled={resendingVerification}
                        onClick={() => void handleResendVerification()}
                        className="text-emerald-700 font-medium hover:underline disabled:opacity-50"
                      >
                        {resendingVerification ? 'Sending...' : 'Resend Verification'}
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-slate-100 text-xs">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                  <div className="text-[11px] text-slate-500">Account Status</div>
                  <div className="font-semibold text-slate-900 mt-0.5">
                    {user.is_active ? 'Active' : 'Inactive'}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                  <div className="text-[11px] text-slate-500">Created On</div>
                  <div className="font-semibold text-slate-900 mt-0.5">
                    {new Date(user.created_at).toLocaleDateString('en-IN')}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                  <div className="text-[11px] text-slate-500">Last Login</div>
                  <div className="font-semibold text-slate-900 mt-0.5">
                    {user.last_login_at ? new Date(user.last_login_at).toLocaleString('en-IN') : 'Current'}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => onNavigate('onboarding')}
                  className="inline-flex items-center space-x-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
                >
                  <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Revisit Onboarding Setup</span>
                </button>
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => setFullName(user.full_name)}
                    className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="inline-flex items-center space-x-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />
                    <span>{savingProfile ? 'Saving...' : 'Save Profile'}</span>
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* 2. SECURITY & SESSIONS */}
          {activeTab === 'security' && (
            <div className="space-y-5">
              <form
                onSubmit={(e) => void handleChangePassword(e)}
                className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-4"
              >
                <div className="border-b border-slate-100 pb-3 flex items-center space-x-2">
                  <KeyRound className="w-4 h-4 text-emerald-600" />
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Change Password</h3>
                    <p className="text-xs text-slate-500">
                      Secured with Argon2id hashing and optional invalidation of all other active sessions.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label htmlFor="cur-pwd" className="block text-xs font-medium text-slate-700 mb-1">
                      Current Password
                    </label>
                    <input
                      id="cur-pwd"
                      type="password"
                      required
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label htmlFor="new-pwd" className="block text-xs font-medium text-slate-700 mb-1">
                      New Password
                    </label>
                    <input
                      id="new-pwd"
                      type="password"
                      required
                      minLength={8}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label htmlFor="conf-pwd" className="block text-xs font-medium text-slate-700 mb-1">
                      Confirm New Password
                    </label>
                    <input
                      id="conf-pwd"
                      type="password"
                      required
                      minLength={8}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                    />
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
                  <label className="inline-flex items-center space-x-2 text-xs text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={revokeOtherSessions}
                      onChange={(e) => setRevokeOtherSessions(e.target.checked)}
                      className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                    />
                    <span>Sign out all other devices after updating password</span>
                  </label>

                  <button
                    type="submit"
                    disabled={changingPassword}
                    className="inline-flex items-center space-x-1.5 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-lg disabled:opacity-50 self-start"
                  >
                    <Lock className="w-3.5 h-3.5" />
                    <span>{changingPassword ? 'Updating...' : 'Update Password'}</span>
                  </button>
                </div>
              </form>

              <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Active Sessions</h3>
                    <p className="text-xs text-slate-500">
                      Tokens are hashed server-side; only device metadata and expiration timestamps are visible.
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      type="button"
                      onClick={() => void loadSessions()}
                      disabled={loadingSessions}
                      className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${loadingSessions ? 'animate-spin' : ''}`} />
                      <span>Refresh</span>
                    </button>
                    <button
                      type="button"
                      disabled={sessions.length === 0}
                      onClick={() => setConfirmSessionAction({ type: 'all' })}
                      className="px-3 py-1.5 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-lg hover:bg-rose-100 disabled:opacity-50"
                    >
                      Log Out All Devices
                    </button>
                  </div>
                </div>

                {loadingSessions && sessions.length === 0 ? (
                  <p className="text-xs text-slate-500 py-4 text-center">Loading active sessions...</p>
                ) : sessions.length === 0 ? (
                  <p className="text-xs text-slate-500 py-4 text-center">No active sessions returned.</p>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {sessions.map((s) => {
                      const isMobile =
                        (s.user_agent || '').toLowerCase().includes('mobile') ||
                        (s.user_agent || '').toLowerCase().includes('android');
                      const DevIcon = isMobile ? Smartphone : Monitor;
                      return (
                        <div key={s.id} className="py-3 flex items-center justify-between gap-3">
                          <div className="flex items-start space-x-3">
                            <DevIcon className="w-4 h-4 text-slate-500 mt-0.5" />
                            <div>
                              <div className="text-xs font-semibold text-slate-900 flex items-center space-x-2">
                                <span>{s.user_agent ? s.user_agent.slice(0, 64) : 'Web Browser Session'}</span>
                                {s.is_current && (
                                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                                    Current Session
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-slate-500 mt-0.5">
                                IP: {s.ip_address || 'Local'} • Last active:{' '}
                                {new Date(s.last_used_at).toLocaleString('en-IN')}
                              </div>
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() => setConfirmSessionAction({ type: 'single', session: s })}
                            className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-lg hover:bg-rose-100"
                          >
                            <Trash2 className="w-3 h-3" />
                            <span>{s.is_current ? 'Sign Out' : 'Revoke'}</span>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 3. PREFERENCES & LOCALIZATION */}
          {activeTab === 'localization' && (
            <form
              onSubmit={(e) => void handleSaveUserPreferences(e)}
              className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-5"
            >
              <div className="border-b border-slate-100 pb-3">
                <h3 className="text-sm font-semibold text-slate-900">Preferences & Localization</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Configure display defaults for India (INR, en-IN Lakhs/Crores, Asia/Kolkata). Changing display formatting never modifies historical ledger amounts or transaction currencies.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="pref-currency" className="block text-xs font-medium text-slate-700 mb-1">
                    Display Currency
                  </label>
                  <select
                    id="pref-currency"
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                  >
                    <option value="INR">INR (₹) — Indian Rupee (Default)</option>
                    <option value="USD">USD ($) — US Dollar</option>
                    <option value="EUR">EUR (€) — Euro</option>
                    <option value="GBP">GBP (£) — British Pound</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="pref-locale" className="block text-xs font-medium text-slate-700 mb-1">
                    Number Format Locale
                  </label>
                  <select
                    id="pref-locale"
                    value={locale}
                    onChange={(e) => setLocale(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                  >
                    <option value="en-IN">en-IN (₹1,00,000.00 — Lakhs & Crores)</option>
                    <option value="en-US">en-US ($100,000.00 — Millions)</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="pref-tz" className="block text-xs font-medium text-slate-700 mb-1">
                    Timezone
                  </label>
                  <select
                    id="pref-tz"
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                  >
                    <option value="Asia/Kolkata">Asia/Kolkata (IST +05:30)</option>
                    <option value="UTC">UTC</option>
                    <option value="America/New_York">America/New_York</option>
                    <option value="Europe/London">Europe/London</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="pref-date" className="block text-xs font-medium text-slate-700 mb-1">
                    Date Format
                  </label>
                  <select
                    id="pref-date"
                    value={dateFormat}
                    onChange={(e) => setDateFormat(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                  >
                    <option value="DD/MM/YYYY">DD/MM/YYYY (Indian Standard)</option>
                    <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                    <option value="YYYY-MM-DD">YYYY-MM-DD (ISO)</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="pref-week" className="block text-xs font-medium text-slate-700 mb-1">
                    Week Starts On
                  </label>
                  <select
                    id="pref-week"
                    value={weekStart}
                    onChange={(e) => setWeekStart(e.target.value as 'monday' | 'sunday')}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                  >
                    <option value="monday">Monday</option>
                    <option value="sunday">Sunday</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="pref-lang" className="block text-xs font-medium text-slate-700 mb-1">
                    Interface Language
                  </label>
                  <select
                    id="pref-lang"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                  >
                    <option value="en-IN">English (India — Supported)</option>
                    <option value="en-US">English (US — Formatting Only)</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={syncPrefsFromContext}
                  className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingPrefs}
                  className="inline-flex items-center space-x-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{savingPrefs ? 'Saving...' : 'Save Localization'}</span>
                </button>
              </div>
            </form>
          )}

          {/* 4. NOTIFICATIONS & REMINDERS */}
          {activeTab === 'notifications' && (
            <form
              onSubmit={(e) => void handleSaveUserPreferences(e)}
              className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-5"
            >
              <div className="border-b border-slate-100 pb-3">
                <h3 className="text-sm font-semibold text-slate-900">Notifications & Reminders</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Control reminder scheduling categories without deleting underlying bills, subscriptions, or loan EMIs.
                </p>
              </div>

              {smtpItem && (
                <div
                  className={`p-3 rounded-xl border text-xs flex items-center justify-between gap-3 ${
                    smtpItem.connected
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                      : 'bg-amber-50 border-amber-200 text-amber-900'
                  }`}
                >
                  <span>
                    <strong>Email Transport Status:</strong>{' '}
                    {smtpItem.connected
                      ? `SMTP active via ${String(smtpItem.safe_metadata.host || '')}:${String(
                          smtpItem.safe_metadata.port || ''
                        )}`
                      : 'SMTP is currently unconfigured on the server (in-app notifications remain active).'}
                  </span>
                  <button
                    type="button"
                    onClick={() => onNavigate('integrations')}
                    className="px-2.5 py-1 bg-white border border-slate-300 rounded-lg text-[11px] font-medium text-slate-700 hover:bg-slate-50 flex-shrink-0"
                  >
                    Inspect SMTP
                  </button>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  { label: 'Upcoming Bill Reminders', state: billReminders, set: setBillReminders },
                  { label: 'Subscription Renewal Alerts', state: subscriptionReminders, set: setSubscriptionReminders },
                  { label: 'Loan EMI Reminders', state: loanEmiReminders, set: setLoanEmiReminders },
                  { label: 'Payment Due Master Switch', state: paymentDueReminders, set: setPaymentDueReminders },
                  { label: 'AI Financial Insights Alerts', state: financialInsights, set: setFinancialInsights },
                  { label: 'Spending Anomaly Alerts', state: spendingAnomalies, set: setSpendingAnomalies },
                  { label: 'Cashflow Forecast Alerts', state: forecastNotifications, set: setForecastNotifications },
                  { label: 'Monthly Cash-Flow Summary', state: monthlySummary, set: setMonthlySummary },
                  { label: 'General Email Alerts', state: emailAlerts, set: setEmailAlerts },
                  { label: 'Email Bill/EMI Reminders', state: emailRemindersEnabled, set: setEmailRemindersEnabled },
                ].map((toggle) => (
                  <label
                    key={toggle.label}
                    className="flex items-center justify-between p-3 rounded-xl border border-slate-200/80 hover:bg-slate-50 cursor-pointer"
                  >
                    <span className="text-xs font-medium text-slate-800">{toggle.label}</span>
                    <input
                      type="checkbox"
                      checked={toggle.state}
                      onChange={(e) => toggle.set(e.target.checked)}
                      className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                    />
                  </label>
                ))}
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-3">
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-xs font-medium text-slate-800">
                    SMS Outbound Reminders Opt-In (+91 Mobile)
                  </span>
                  <input
                    type="checkbox"
                    checked={smsRemindersEnabled}
                    onChange={(e) => setSmsRemindersEnabled(e.target.checked)}
                    className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                </label>
                <input
                  type="tel"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+91 9876543210"
                  aria-label="Indian mobile number for SMS reminders"
                  className="w-full sm:w-72 px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={syncPrefsFromContext}
                  className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingPrefs}
                  className="inline-flex items-center space-x-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{savingPrefs ? 'Saving...' : 'Save Notifications'}</span>
                </button>
              </div>
            </form>
          )}

          {/* 5. AI ASSISTANT PREFERENCES */}
          {activeTab === 'ai' && (
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-5">
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">AI Assistant & Web Research</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Backed by your Phase 10 <code>user_ai_preferences</code> row. Changes take effect immediately in AI Assistant.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onNavigate('integrations')}
                  className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200"
                >
                  <Plug className="w-3.5 h-3.5" />
                  <span>Integrations</span>
                </button>
              </div>

              {!aiPrefs ? (
                <p className="text-xs text-slate-500 py-4 text-center">Loading AI preferences...</p>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label
                      htmlFor="ai-web-provider"
                      className="block text-xs font-medium text-slate-700 mb-1"
                    >
                      Preferred Web Research Provider (No Silent Fallback)
                    </label>
                    <select
                      id="ai-web-provider"
                      disabled={savingAiPrefs}
                      value={aiPrefs.default_web_provider}
                      onChange={(e) =>
                        void handleSaveAiPreferences({
                          default_web_provider: e.target.value as WebProviderId,
                        })
                      }
                      className="w-full sm:w-80 px-3 py-2 text-xs border border-slate-300 rounded-lg"
                    >
                      <option value="tavily">Tavily Search</option>
                      <option value="langsearch">LangSearch Web Search</option>
                      <option value="firecrawl">Firecrawl Search & Scrape</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                    {webProviders.map((wp) => (
                      <div
                        key={wp.provider}
                        className="p-3 rounded-xl border border-slate-200/80 bg-slate-50 text-xs"
                      >
                        <div className="font-semibold text-slate-900">{wp.display_name}</div>
                        <div
                          className={`text-[11px] mt-1 font-medium ${
                            wp.configured ? 'text-emerald-700' : 'text-amber-700'
                          }`}
                        >
                          {wp.configured ? 'Server Key Configured' : 'Unconfigured on Server'}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2.5">
                    <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 cursor-pointer">
                      <div>
                        <div className="text-xs font-medium text-slate-900">Enable External Web Research</div>
                        <div className="text-[11px] text-slate-500">
                          Allow assistant queries to cite sanitized public Indian tax/RBI guidance.
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        disabled={savingAiPrefs}
                        checked={aiPrefs.web_search_enabled}
                        onChange={(e) =>
                          void handleSaveAiPreferences({ web_search_enabled: e.target.checked })
                        }
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                      />
                    </label>

                    <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 cursor-pointer">
                      <div>
                        <div className="text-xs font-medium text-slate-900">Voice Read Aloud Auto-Speak</div>
                        <div className="text-[11px] text-slate-500">
                          Keep off to trigger Read Aloud manually per assistant reply.
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        disabled={savingAiPrefs}
                        checked={aiPrefs.voice_read_aloud_enabled}
                        onChange={(e) =>
                          void handleSaveAiPreferences({ voice_read_aloud_enabled: e.target.checked })
                        }
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                      />
                    </label>

                    <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 cursor-pointer">
                      <div>
                        <div className="text-xs font-medium text-slate-900">
                          Auto-Create Bills & Subscriptions from Chat Commands
                        </div>
                        <div className="text-[11px] text-slate-500">
                          When off, AI chat always displays an interactive review card for confirmation before writing.
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        disabled={savingAiPrefs}
                        checked={aiPrefs.auto_execute_actions}
                        onChange={(e) =>
                          void handleSaveAiPreferences({ auto_execute_actions: e.target.checked })
                        }
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                      />
                    </label>
                  </div>

                  {groqInfo && (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-700">
                      <strong>LLM Inference Backend:</strong> {groqInfo.name} —{' '}
                      {groqInfo.available
                        ? `Enabled (${String(groqInfo.safe_metadata.model_name || '')})`
                        : 'Disabled or unconfigured on server (deterministic engine active).'}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 6. PRIVACY & DATA MANAGEMENT */}
          {activeTab === 'privacy' && (
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-5">
              <div className="border-b border-slate-100 pb-3">
                <h3 className="text-sm font-semibold text-slate-900">Privacy & Data Management</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Review your tenant-scoped financial records, storage protections, CSV exports, and deletion safeguards.
                </p>
              </div>

              {loadingPrivacy || !privacySummary ? (
                <p className="text-xs text-slate-500 py-4 text-center">Loading data inventory...</p>
              ) : (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 text-center">
                    {[
                      { k: 'Accounts', v: privacySummary.accounts_count },
                      { k: 'Transactions', v: privacySummary.transactions_count },
                      { k: 'Bills & Subs', v: privacySummary.bills_count + privacySummary.subscriptions_count },
                      { k: 'Documents', v: privacySummary.documents_count },
                      { k: 'AI Chats', v: privacySummary.conversations_count },
                    ].map((stat) => (
                      <div key={stat.k} className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
                        <div className="text-lg font-bold text-slate-900">{stat.v}</div>
                        <div className="text-[11px] text-slate-500">{stat.k}</div>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-slate-800 flex items-center space-x-1.5">
                      <Shield className="w-3.5 h-3.5 text-emerald-600" />
                      <span>How Your Data Is Protected</span>
                    </h4>
                    <ul className="space-y-1.5 text-xs text-slate-600 list-disc pl-5">
                      {privacySummary.data_storage_disclosures.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="space-y-2.5 pt-2 border-t border-slate-100">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h4 className="text-xs font-semibold text-slate-800">Available Data Exports & Documents</h4>
                      <button
                        type="button"
                        onClick={() => onNavigate('documents')}
                        className="text-xs font-medium text-emerald-700 hover:underline"
                      >
                        Manage Uploaded Documents →
                      </button>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                      {privacySummary.export_endpoints.map((exp) => (
                        <button
                          key={exp.endpoint}
                          type="button"
                          onClick={() => handleExportCsv(exp.endpoint)}
                          className="p-3 rounded-xl border border-slate-200 hover:bg-slate-50 text-left space-y-1 transition-colors"
                        >
                          <div className="text-xs font-semibold text-slate-900 flex items-center space-x-1.5">
                            <Download className="w-3.5 h-3.5 text-emerald-600" />
                            <span>{exp.label}</span>
                          </div>
                          <div className="text-[11px] text-slate-500">{exp.description}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
                    <div className="font-semibold">Account Deletion Status: Deferred</div>
                    <p className="text-[11px] leading-relaxed">{privacySummary.account_deletion_note}</p>
                  </div>
                </>
              )}
            </div>
          )}

          {/* 7. APPLICATION PREFERENCES */}
          {activeTab === 'application' && (
            <form
              onSubmit={(e) => void handleSaveUserPreferences(e)}
              className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 space-y-5"
            >
              <div className="border-b border-slate-100 pb-3">
                <h3 className="text-sm font-semibold text-slate-900">Application Preferences</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Customize genuine workspace defaults persisted to PostgreSQL for your account.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="app-landing"
                    className="block text-xs font-medium text-slate-700 mb-1"
                  >
                    Default Landing Section After Sign-In
                  </label>
                  <select
                    id="app-landing"
                    value={defaultLandingView}
                    onChange={(e) =>
                      setDefaultLandingView(
                        e.target.value as 'dashboard' | 'analytics' | 'assistant' | 'bills' | 'transactions'
                      )
                    }
                    className="w-full sm:w-80 px-3 py-2 text-xs border border-slate-300 rounded-lg"
                  >
                    <option value="dashboard">Financial Dashboard (Default)</option>
                    <option value="analytics">Analytics Overview</option>
                    <option value="assistant">AI Finance Assistant</option>
                    <option value="bills">Bills & Reminders</option>
                    <option value="transactions">Transactions Ledger</option>
                  </select>
                </div>

                <label className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 cursor-pointer">
                  <div>
                    <div className="text-xs font-medium text-slate-900">Compact Sidebar Mode</div>
                    <div className="text-[11px] text-slate-500">
                      Reduces desktop sidebar width and spacing for denser workspace views.
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={compactSidebar}
                    onChange={(e) => setCompactSidebar(e.target.checked)}
                    className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                </label>

                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-[11px] text-slate-600">
                  <strong>Theme Mode:</strong> Light financial slate theme is active (dark theme switching is not configured in this release).
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={syncPrefsFromContext}
                  className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingPrefs}
                  className="inline-flex items-center space-x-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{savingPrefs ? 'Saving...' : 'Save Application Settings'}</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* Confirmation Modal for Session Revocation */}
      {confirmSessionAction && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="session-confirm-title"
        >
          <div className="bg-white rounded-2xl border border-slate-200 max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 id="session-confirm-title" className="text-base font-bold text-slate-900">
              {confirmSessionAction.type === 'all'
                ? 'Log Out From All Devices?'
                : confirmSessionAction.session.is_current
                ? 'Sign Out of Current Session?'
                : 'Revoke Selected Session?'}
            </h3>
            <p className="text-xs text-slate-600">
              {confirmSessionAction.type === 'all'
                ? 'All active sessions including your current browser will be invalidated immediately.'
                : confirmSessionAction.session.is_current
                ? 'You will be signed out of this browser and redirected to the sign-in screen.'
                : 'That device will no longer have access until the user signs in again.'}
            </p>
            <div className="flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setConfirmSessionAction(null)}
                className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmSessionAction()}
                className="px-3 py-1.5 text-xs font-medium text-white bg-rose-600 rounded-lg hover:bg-rose-700"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
