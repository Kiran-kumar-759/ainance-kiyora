import React, { useState, useEffect } from 'react';
import { Bell, Globe, Save, CheckCircle2, AlertCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface PreferencesPageProps {
  onNavigate?: (view: string) => void;
}

export const PreferencesPage: React.FC<PreferencesPageProps> = () => {
  const { preferences, updatePreferences } = useAuth();
  const [currency, setCurrency] = useState(preferences?.preferred_currency || 'INR');
  const [locale, setLocale] = useState(preferences?.locale || 'en-IN');
  const [timezone, setTimezone] = useState(preferences?.timezone || 'Asia/Kolkata');
  const [dateFormat, setDateFormat] = useState(preferences?.date_format || 'DD/MM/YYYY');

  const [emailAlerts, setEmailAlerts] = useState(preferences?.notification_preferences?.email_alerts ?? true);
  const [billReminders, setBillReminders] = useState(preferences?.notification_preferences?.bill_reminders ?? true);
  const [monthlySummary, setMonthlySummary] = useState(preferences?.notification_preferences?.monthly_summary ?? true);
  const [emailRemindersEnabled, setEmailRemindersEnabled] = useState(
    Boolean(preferences?.notification_preferences?.email_reminders_enabled ?? true)
  );
  const [smsRemindersEnabled, setSmsRemindersEnabled] = useState(
    Boolean(preferences?.notification_preferences?.sms_reminders_enabled ?? false)
  );
  const [phoneNumber, setPhoneNumber] = useState(
    String(preferences?.notification_preferences?.phone_number || '')
  );

  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (preferences) {
      setCurrency(preferences.preferred_currency || 'INR');
      setLocale(preferences.locale || 'en-IN');
      setTimezone(preferences.timezone || 'Asia/Kolkata');
      setDateFormat(preferences.date_format || 'DD/MM/YYYY');
      if (preferences.notification_preferences) {
        setEmailAlerts(preferences.notification_preferences.email_alerts ?? true);
        setBillReminders(preferences.notification_preferences.bill_reminders ?? true);
        setMonthlySummary(preferences.notification_preferences.monthly_summary ?? true);
        setEmailRemindersEnabled(
          Boolean(preferences.notification_preferences.email_reminders_enabled ?? true)
        );
        setSmsRemindersEnabled(
          Boolean(preferences.notification_preferences.sms_reminders_enabled ?? false)
        );
        setPhoneNumber(String(preferences.notification_preferences.phone_number || ''));
      }
    }
  }, [preferences]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMessage(null);

    try {
      const payload = {
        preferred_currency: currency,
        locale,
        timezone,
        date_format: dateFormat,
        notification_preferences: {
          email_alerts: emailAlerts,
          bill_reminders: billReminders,
          monthly_summary: monthlySummary,
          email_reminders_enabled: emailRemindersEnabled,
          sms_reminders_enabled: smsRemindersEnabled,
          phone_number: phoneNumber.trim() || undefined,
        },
      };

      await updatePreferences(payload);
      setStatusMessage({ type: 'success', text: 'Regional & notification preferences saved!' });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save preferences.';
      setStatusMessage({ type: 'error', text: msg });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">Regional & System Preferences</h2>
        <p className="text-xs text-slate-500">
          Customize currency displays, Indian date formats, and alert triggers
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

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Regional Section */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6">
          <div className="flex items-center space-x-2 pb-4 mb-4 border-b border-slate-100">
            <Globe className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-semibold text-slate-900">Regional & Financial Formatting</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Preferred Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              >
                <option value="INR">INR (₹) - Indian Rupee (Default)</option>
                <option value="USD">USD ($) - US Dollar</option>
                <option value="EUR">EUR (€) - Euro</option>
                <option value="GBP">GBP (£) - British Pound</option>
              </select>
              <p className="text-[11px] text-slate-400 mt-1">Used for totals, analytics, and projections.</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Number & Decimal Locale
              </label>
              <select
                value={locale}
                onChange={(e) => setLocale(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              >
                <option value="en-IN">en-IN (₹1,00,000.00 - Lakhs & Crores)</option>
                <option value="en-US">en-US ($100,000.00 - Millions)</option>
              </select>
              <p className="text-[11px] text-slate-400 mt-1">Controls comma grouping separators.</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Timezone
              </label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              >
                <option value="Asia/Kolkata">Asia/Kolkata (IST +05:30 - Standard)</option>
                <option value="UTC">UTC (Universal Coordinated Time)</option>
                <option value="America/New_York">America/New_York (US Eastern)</option>
                <option value="Europe/London">Europe/London (GMT/BST)</option>
              </select>
              <p className="text-[11px] text-slate-400 mt-1">Used to record transaction and bill timestamps.</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Date Format
              </label>
              <select
                value={dateFormat}
                onChange={(e) => setDateFormat(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              >
                <option value="DD/MM/YYYY">DD/MM/YYYY (Indian Standard)</option>
                <option value="YYYY-MM-DD">YYYY-MM-DD (ISO Standard)</option>
                <option value="MM/DD/YYYY">MM/DD/YYYY (US Format)</option>
              </select>
              <p className="text-[11px] text-slate-400 mt-1">Used across statement displays and date pickers.</p>
            </div>
          </div>
        </div>

        {/* Notifications Section */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6">
          <div className="flex items-center space-x-2 pb-4 mb-4 border-b border-slate-100">
            <Bell className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-semibold text-slate-900">Communication & Alert Preferences</h3>
          </div>

          <div className="space-y-3">
            <label className="flex items-center justify-between p-3 border border-slate-200 rounded-xl hover:bg-slate-50 cursor-pointer">
              <div>
                <div className="text-xs font-semibold text-slate-800">Security & Sign-in Alerts</div>
                <div className="text-[11px] text-slate-500">Receive notifications on new logins or credential updates</div>
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
                <div className="text-xs font-semibold text-slate-800">Bill & Loan EMI Reminders</div>
                <div className="text-[11px] text-slate-500">Alerts 3 days before payment due dates</div>
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
                <div className="text-[11px] text-slate-500">Automated summary of monthly cash flow and savings rate</div>
              </div>
              <input
                type="checkbox"
                checked={monthlySummary}
                onChange={(e) => setMonthlySummary(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
            </label>

            <label className="flex items-center justify-between p-3 border border-slate-200 rounded-xl hover:bg-slate-50 cursor-pointer">
              <div>
                <div className="text-xs font-semibold text-slate-800">Email Bill Reminders</div>
                <div className="text-[11px] text-slate-500">Allow due-date reminder emails when SMTP is configured</div>
              </div>
              <input
                type="checkbox"
                checked={emailRemindersEnabled}
                onChange={(e) => setEmailRemindersEnabled(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
            </label>

            <div className="p-3 border border-slate-200 rounded-xl space-y-2">
              <label className="flex items-center justify-between cursor-pointer">
                <div>
                  <div className="text-xs font-semibold text-slate-800">SMS Bill Reminders (Opt-In)</div>
                  <div className="text-[11px] text-slate-500">Requires Indian mobile number and configured SMS provider</div>
                </div>
                <input
                  type="checkbox"
                  checked={smsRemindersEnabled}
                  onChange={(e) => setSmsRemindersEnabled(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
              </label>
              <div>
                <label className="block text-[11px] font-medium text-slate-700 mb-1">
                  Mobile Number (+91XXXXXXXXXX)
                </label>
                <input
                  type="tel"
                  placeholder="+919876543210"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isSaving}
            className="inline-flex items-center space-x-1.5 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors shadow-xs"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{isSaving ? 'Saving...' : 'Save Preferences'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
