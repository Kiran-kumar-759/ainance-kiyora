import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Archive,
  Check,
  CheckCircle2,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  TrendingUp,
  X,
  XCircle,
} from 'lucide-react';
import { subscriptionsApi } from '../../services/phase6Api';
import { financeApi } from '../../services/financeApi';
import { FinancialAccount, FinancialTransaction } from '../../types/finance';
import {
  Subscription,
  SubscriptionCategory,
  SubscriptionFrequency,
} from '../../types/phase6';
import { PAYMENT_METHODS } from '../bills/BillModals';
import { formatDate, formatINR } from '../../lib/formatters';
import {
  CategoryPictureBadge,
  getCategoryMeta,
  getProvidersForCategory,
  matchProviderPreset,
  ProviderLogo,
  ProviderPreset,
  SUBSCRIPTION_CATEGORY_CATALOG,
} from '../../components/subscriptions/ProviderCatalog';

export const SUBSCRIPTION_CATEGORIES: { id: SubscriptionCategory; label: string }[] =
  SUBSCRIPTION_CATEGORY_CATALOG.map((c) => ({ id: c.id, label: c.label }));

interface SubFormModalProps {
  isOpen: boolean;
  editingSub: Subscription | null;
  accounts: FinancialAccount[];
  initialDraft?: {
    name?: string;
    provider?: string;
    amount?: string;
    frequency?: SubscriptionFrequency;
    nextDate?: string;
  } | null;
  onClose: () => void;
  onSaved: (sub: Subscription) => void;
}

export const SubscriptionFormModal: React.FC<SubFormModalProps> = ({
  isOpen,
  editingSub,
  accounts,
  initialDraft,
  onClose,
  onSaved,
}) => {
  const [name, setName] = useState('');
  const [provider, setProvider] = useState('');
  const [selectedPresetId, setSelectedPresetId] = useState('custom');
  const [category, setCategory] = useState<SubscriptionCategory>('ott_streaming');
  const [planName, setPlanName] = useState('');
  const [amount, setAmount] = useState('');
  const [frequency, setFrequency] = useState<SubscriptionFrequency>('monthly');
  const [customDays, setCustomDays] = useState('30');
  const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0]);
  const [nextRenewal, setNextRenewal] = useState('');
  const [isTrial, setIsTrial] = useState(false);
  const [trialEndDate, setTrialEndDate] = useState('');
  const [linkedAccountId, setLinkedAccountId] = useState('');
  const [method, setMethod] = useState('upi');
  const [notes, setNotes] = useState('');
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [reminderDays, setReminderDays] = useState<number[]>([7, 3, 1, 0]);
  const [emailCh, setEmailCh] = useState(false);
  const [smsCh, setSmsCh] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    if (editingSub) {
      setName(editingSub.subscription_name);
      setProvider(editingSub.provider_name || '');
      const matched = matchProviderPreset(editingSub.subscription_name, editingSub.provider_name);
      setSelectedPresetId(matched ? matched.id : 'custom');
      setCategory(editingSub.category);
      setPlanName(editingSub.plan_name || '');
      setAmount(editingSub.amount ? String(editingSub.amount) : '');
      setFrequency(editingSub.billing_frequency);
      setCustomDays(editingSub.custom_interval_days ? String(editingSub.custom_interval_days) : '30');
      setStartDate(editingSub.start_date);
      setNextRenewal(editingSub.next_renewal_date || '');
      setIsTrial(editingSub.status === 'trial');
      setTrialEndDate(editingSub.trial_end_date || '');
      setLinkedAccountId(editingSub.linked_account_id || '');
      setMethod(editingSub.preferred_payment_method || 'upi');
      setNotes(editingSub.notes || '');
      setReminderEnabled(editingSub.reminder_enabled);
      setReminderDays(editingSub.reminder_days_before || [7, 3, 1, 0]);
      setEmailCh(Boolean(editingSub.notification_channels?.email));
      setSmsCh(Boolean(editingSub.notification_channels?.sms));
    } else {
      const dName = initialDraft?.name || '';
      const dProvider = initialDraft?.provider || '';
      const matched = matchProviderPreset(dName, dProvider);
      setName(dName);
      setProvider(dProvider);
      setSelectedPresetId(matched ? matched.id : 'custom');
      setCategory(matched ? matched.category : 'ott_streaming');
      setPlanName('');
      setAmount(initialDraft?.amount || '');
      setFrequency(initialDraft?.frequency || 'monthly');
      setCustomDays('30');
      const todayStr = new Date().toISOString().split('T')[0];
      setStartDate(todayStr);
      setNextRenewal(initialDraft?.nextDate || '');
      setIsTrial(false);
      setTrialEndDate('');
      setLinkedAccountId('');
      setMethod('upi');
      setNotes('');
      setReminderEnabled(true);
      setReminderDays([7, 3, 1, 0]);
      setEmailCh(false);
      setSmsCh(false);
    }
  }, [isOpen, editingSub, initialDraft]);

  if (!isOpen) return null;

  const categoryProviders = getProvidersForCategory(category);
  const currentCatMeta = getCategoryMeta(category);
  const CurrentCatIcon = currentCatMeta.Icon;

  const applyPreset = (preset: ProviderPreset) => {
    setSelectedPresetId(preset.id);
    setName(preset.name);
    setProvider(preset.providerName);
    if (!planName.trim() && preset.suggestedPlan) {
      setPlanName(preset.suggestedPlan);
    }
  };

  const handleCategoryChange = (nextCat: SubscriptionCategory) => {
    setCategory(nextCat);
    const nextProviders = getProvidersForCategory(nextCat);
    const stillMatches = nextProviders.some((p) => p.id === selectedPresetId);
    if (!stillMatches) {
      setSelectedPresetId('custom');
    }
  };

  const handleProviderDropdownChange = (presetId: string) => {
    if (presetId === 'custom') {
      setSelectedPresetId('custom');
      return;
    }
    const found = categoryProviders.find((p) => p.id === presetId);
    if (found) {
      applyPreset(found);
    }
  };

  const toggleDay = (d: number) =>
    setReminderDays((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort((a, b) => b - a)
    );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    if (!name.trim()) {
      setError('Subscription name is required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        subscription_name: name.trim(),
        provider_name: provider.trim() || null,
        category,
        plan_name: planName.trim() || null,
        amount: amount.trim() ? Number(amount).toFixed(2) : null,
        billing_frequency: frequency,
        custom_interval_days: frequency === 'custom' ? Number(customDays || 30) : null,
        next_renewal_date: nextRenewal || null,
        trial_end_date: isTrial && trialEndDate ? trialEndDate : null,
        linked_account_id: linkedAccountId || null,
        preferred_payment_method: method,
        notes: notes.trim() || null,
        reminder_enabled: reminderEnabled,
        reminder_days_before: reminderDays.length > 0 ? reminderDays : [7, 3, 1, 0],
        notification_channels: { in_app: true, email: emailCh, sms: smsCh },
      };

      let saved: Subscription;
      if (editingSub) {
        saved = await subscriptionsApi.updateSubscription(editingSub.id, payload);
      } else {
        payload.start_date = startDate;
        payload.is_trial = isTrial;
        if (isTrial) payload.trial_start_date = startDate;
        saved = await subscriptionsApi.createSubscription(payload);
      }
      onSaved(saved);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save subscription.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-xl relative max-h-[92vh] overflow-y-auto text-xs">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>
        <h3 className="text-lg font-bold text-gray-900">
          {editingSub ? 'Edit Subscription' : 'Add OTT / Recurring Subscription'}
        </h3>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5 mt-4">
          {/* Category Visual Selector (Pictures) */}
          <div className="space-y-2">
            <label className="block font-semibold text-gray-700">Select Category</label>
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-1.5">
              {SUBSCRIPTION_CATEGORY_CATALOG.map((cat) => {
                const Icon = cat.Icon;
                const active = category === cat.id;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => handleCategoryChange(cat.id)}
                    className={`flex items-center space-x-1.5 px-2 py-1.5 rounded-lg border text-left transition-all ${
                      active
                        ? `${cat.bgClass} ${cat.textClass} ${cat.borderClass} ring-1 ring-offset-0 ring-current font-semibold shadow-xs`
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <span
                      className={`w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 ${cat.bgClass} ${cat.textClass}`}
                    >
                      <Icon className="w-3 h-3" />
                    </span>
                    <span className="truncate text-[10px]">{cat.shortLabel}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Category Dropdown + Provider Dropdown beside it (with pictures) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 bg-slate-50/80 border border-slate-200 rounded-xl">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Category *</label>
              <div className="flex items-center space-x-2">
                <span
                  className={`w-9 h-9 rounded-lg flex items-center justify-center border flex-shrink-0 ${currentCatMeta.bgClass} ${currentCatMeta.textClass} ${currentCatMeta.borderClass}`}
                  title={currentCatMeta.label}
                >
                  <CurrentCatIcon className="w-4 h-4" />
                </span>
                <select
                  aria-label="Subscription Category"
                  value={category}
                  onChange={(e) => handleCategoryChange(e.target.value as SubscriptionCategory)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white font-medium"
                >
                  {SUBSCRIPTION_CATEGORIES.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Provider Preset ({currentCatMeta.shortLabel})
              </label>
              <div className="flex items-center space-x-2">
                <ProviderLogo
                  category={category}
                  subscriptionName={name}
                  providerName={provider}
                  size="sm"
                />
                <select
                  aria-label="Provider Preset"
                  value={selectedPresetId}
                  onChange={(e) => handleProviderDropdownChange(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white font-medium"
                >
                  <option value="custom">Custom / Type provider below...</option>
                  {categoryProviders.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Visual Quick-Pick Logos for the selected category */}
            {categoryProviders.length > 0 && (
              <div className="sm:col-span-2 pt-1">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 mb-1.5">
                  Quick Pick {currentCatMeta.shortLabel} Logos (or type custom below)
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {categoryProviders.slice(0, 6).map((preset) => {
                    const isPicked = selectedPresetId === preset.id;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => applyPreset(preset)}
                        className={`inline-flex items-center space-x-1.5 pl-1 pr-2 py-1 rounded-lg border text-[11px] font-medium transition-all ${
                          isPicked
                            ? 'bg-blue-50 border-blue-400 text-blue-800 shadow-xs'
                            : 'bg-white border-gray-200 text-gray-700 hover:border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        <ProviderLogo
                          category={preset.category}
                          subscriptionName={preset.name}
                          providerName={preset.providerName}
                          size="sm"
                          className="!w-5 !h-5 !rounded-md !text-[8px]"
                        />
                        <span>{preset.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Text Inputs beside Logo Preview (allows typing any provider/name manually too) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Subscription Name (Type or Picked) *
              </label>
              <input
                type="text"
                required
                placeholder="e.g., Netflix, Amazon Prime, Google One"
                value={name}
                onChange={(e) => {
                  const val = e.target.value;
                  setName(val);
                  const matched = matchProviderPreset(val, provider);
                  setSelectedPresetId(matched && matched.category === category ? matched.id : 'custom');
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Provider / Merchant (Type Custom)
              </label>
              <input
                type="text"
                placeholder="e.g., Netflix India, Apple, Custom"
                value={provider}
                onChange={(e) => {
                  const val = e.target.value;
                  setProvider(val);
                  const matched = matchProviderPreset(name, val);
                  setSelectedPresetId(matched && matched.category === category ? matched.id : 'custom');
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Plan Name</label>
              <input
                type="text"
                placeholder="e.g., Mobile HD, Family"
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Amount (₹)</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                placeholder="Leave blank if trial/TBD"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Billing Cycle</label>
              <select
                aria-label="Billing Frequency"
                value={frequency}
                onChange={(e) => setFrequency(e.target.value as SubscriptionFrequency)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="half_yearly">Half-Yearly</option>
                <option value="yearly">Yearly</option>
                <option value="custom">Custom Days</option>
              </select>
            </div>
            {frequency === 'custom' && (
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Interval (Days)</label>
                <input
                  type="number"
                  min="1"
                  value={customDays}
                  onChange={(e) => setCustomDays(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            )}
            {!editingSub && (
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Start Date *</label>
                <input
                  type="date"
                  required
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            )}
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Next Renewal Date</label>
              <input
                type="date"
                value={nextRenewal}
                onChange={(e) => setNextRenewal(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
            <label className="flex items-center space-x-2 cursor-pointer font-semibold text-gray-800">
              <input
                type="checkbox"
                checked={isTrial}
                onChange={(e) => setIsTrial(e.target.checked)}
                className="rounded border-gray-300 text-blue-600"
              />
              <span>Active Free Trial (Reminder before trial ends)</span>
            </label>
            {isTrial && (
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Trial End Date</label>
                <input
                  type="date"
                  value={trialEndDate}
                  onChange={(e) => setTrialEndDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Default Payment Method</label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                {PAYMENT_METHODS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Linked Payment Account</label>
              <select
                value={linkedAccountId}
                onChange={(e) => setLinkedAccountId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="">None (Choose at payment time)</option>
                {accounts
                  .filter((a) => a.account_type !== 'loan_liability')
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({formatINR(a.current_balance)})
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <div className="p-3 bg-indigo-50/40 border border-indigo-100 rounded-xl space-y-2">
            <label className="flex items-center space-x-2 cursor-pointer font-semibold text-gray-900">
              <input
                type="checkbox"
                checked={reminderEnabled}
                onChange={(e) => setReminderEnabled(e.target.checked)}
                className="rounded border-gray-300 text-indigo-600"
              />
              <span>Enable Renewal &amp; Trial Reminders</span>
            </label>
            {reminderEnabled && (
              <div className="flex flex-wrap gap-2 items-center">
                {[7, 5, 3, 1, 0].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => toggleDay(d)}
                    className={`px-2 py-1 rounded border text-[11px] font-medium ${
                      reminderDays.includes(d)
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-white text-gray-600 border-gray-300'
                    }`}
                  >
                    {d === 0 ? 'Same Day' : `${d}d before`}
                  </button>
                ))}
                <label className="flex items-center space-x-1 ml-2">
                  <input type="checkbox" checked={emailCh} onChange={(e) => setEmailCh(e.target.checked)} />
                  <span>Email</span>
                </label>
                <label className="flex items-center space-x-1">
                  <input type="checkbox" checked={smsCh} onChange={(e) => setSmsCh(e.target.checked)} />
                  <span>SMS</span>
                </label>
              </div>
            )}
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">Notes</label>
            <input
              type="text"
              placeholder="Optional notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-gray-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium text-gray-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-semibold inline-flex items-center space-x-1.5"
            >
              {submitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
              <span>{editingSub ? 'Save Changes' : 'Add Subscription'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface SubPaymentModalProps {
  sub: Subscription | null;
  accounts: FinancialAccount[];
  onClose: () => void;
  onRecorded: (updated: Subscription) => void;
}

export const SubscriptionPaymentModal: React.FC<SubPaymentModalProps> = ({
  sub,
  accounts,
  onClose,
  onRecorded,
}) => {
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [accountId, setAccountId] = useState('');
  const [method, setMethod] = useState('upi');
  const [ref, setRef] = useState('');
  const [advanceRenewal, setAdvanceRenewal] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idemKey, setIdemKey] = useState('');

  useEffect(() => {
    if (!sub) return;
    setError(null);
    setIdemKey(`subpay-${sub.id}-${Date.now()}`);
    setAmount(sub.amount ? String(sub.amount) : '');
    setDate(new Date().toISOString().split('T')[0]);
    const payAccs = accounts.filter((a) => a.account_type !== 'loan_liability');
    setAccountId(sub.linked_account_id || payAccs[0]?.id || '');
    setMethod(sub.preferred_payment_method || 'upi');
    setRef('');
    setAdvanceRenewal(true);
  }, [sub, accounts]);

  if (!sub) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await subscriptionsApi.recordPayment(sub.id, {
        amount_paid: Number(amount).toFixed(2),
        payment_date: date,
        financial_account_id: accountId,
        payment_method: method,
        reference_number: ref.trim() || undefined,
        idempotency_key: idemKey,
        advance_renewal_date: advanceRenewal,
      });
      onRecorded(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to record payment.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl relative text-xs">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>
        <div className="flex items-center space-x-3 pr-8">
          <ProviderLogo
            category={sub.category}
            subscriptionName={sub.subscription_name}
            providerName={sub.provider_name}
            size="md"
          />
          <div>
            <h3 className="text-lg font-bold text-gray-900">Pay Subscription Bill</h3>
            <p className="text-gray-500 mt-0.5">
              {sub.subscription_name}
              {sub.provider_name ? ` • ${sub.provider_name}` : ''}
            </p>
          </div>
        </div>

        <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-900 flex items-start space-x-2">
          <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <span>
            <strong>Manual Payment Recording Only:</strong> Records a completed charge into your
            financial ledger. Does not initiate live UPI or card charges.
          </span>
        </div>

        {error && (
          <div className="mt-3 p-2.5 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3 mt-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Amount (₹) *</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Payment Date *</label>
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">Payment Account *</label>
            <select
              required
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
            >
              {accounts
                .filter((a) => a.account_type !== 'loan_liability')
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({formatINR(a.current_balance)})
                  </option>
                ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Method</label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                {PAYMENT_METHODS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Reference</label>
              <input
                type="text"
                value={ref}
                onChange={(e) => setRef(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="checkbox"
              checked={advanceRenewal}
              onChange={(e) => setAdvanceRenewal(e.target.checked)}
              className="rounded border-gray-300 text-emerald-600"
            />
            <span className="text-gray-700">Advance next renewal date automatically</span>
          </label>

          <div className="flex justify-end space-x-2 pt-3 border-t border-gray-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-100 rounded-lg text-gray-700 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold inline-flex items-center space-x-1"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Confirm Payment</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface SubDetailsModalProps {
  sub: Subscription | null;
  onClose: () => void;
  onEdit: (s: Subscription) => void;
  onRecordPayment: (s: Subscription) => void;
  onUpdated: (s: Subscription) => void;
}

export const SubscriptionDetailsModal: React.FC<SubDetailsModalProps> = ({
  sub,
  onClose,
  onEdit,
  onRecordPayment,
  onUpdated,
}) => {
  const [newPrice, setNewPrice] = useState('');
  const [effDate, setEffDate] = useState(new Date().toISOString().split('T')[0]);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showLinkTx, setShowLinkTx] = useState(false);
  const [recentTxs, setRecentTxs] = useState<FinancialTransaction[]>([]);
  const [selectedTxId, setSelectedTxId] = useState('');

  useEffect(() => {
    if (!sub) return;
    setNewPrice(sub.amount ? String(sub.amount) : '');
    setReason('');
    setErr(null);
    setShowLinkTx(false);
  }, [sub]);

  if (!sub) return null;

  const runAction = async (fn: () => Promise<Subscription>) => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fn();
      onUpdated(res);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  const handlePriceUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPrice) return;
    await runAction(() =>
      subscriptionsApi.changePrice(sub.id, {
        new_price: Number(newPrice).toFixed(2),
        effective_date: effDate,
        reason: reason.trim() || undefined,
      })
    );
  };

  const openLinkTx = async () => {
    setShowLinkTx(true);
    const res = await financeApi.listTransactions({
      transaction_type: 'expense',
      page: 1,
      page_size: 20,
    });
    setRecentTxs(res.items);
    if (res.items[0]) setSelectedTxId(res.items[0].id);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl relative max-h-[92vh] overflow-y-auto text-xs space-y-5">
        <button
          type="button"
          aria-label="Close modal"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex flex-wrap items-start justify-between gap-3 pr-8">
          <div className="flex items-start space-x-3">
            <ProviderLogo
              category={sub.category}
              subscriptionName={sub.subscription_name}
              providerName={sub.provider_name}
              size="lg"
            />
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-lg font-bold text-gray-900">{sub.subscription_name}</h3>
                <CategoryPictureBadge category={sub.category} />
              </div>
              <p className="text-gray-500 mt-0.5">
                {sub.provider_name || 'Personal'}
                {sub.plan_name ? ` • ${sub.plan_name}` : ''} •{' '}
                <span className="capitalize">{sub.billing_frequency.replace('_', ' ')}</span> • Status:{' '}
                <strong className="uppercase">{sub.status}</strong>
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {sub.status !== 'archived' && sub.status !== 'cancelled' && (
              <>
                <button
                  type="button"
                  onClick={() => onRecordPayment(sub)}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold inline-flex items-center space-x-1"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Pay Bill</span>
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => runAction(() => subscriptionsApi.advanceRenewal(sub.id))}
                  className="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-lg font-semibold inline-flex items-center space-x-1"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Mark as Paid</span>
                </button>
              </>
            )}
            {(sub.status === 'active' || sub.status === 'trial') && (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction(() => subscriptionsApi.pauseSubscription(sub.id))}
                className="px-3 py-1.5 bg-amber-50 text-amber-800 border border-amber-200 rounded-lg font-medium inline-flex items-center space-x-1"
              >
                <PauseCircle className="w-3.5 h-3.5" />
                <span>Pause</span>
              </button>
            )}
            {sub.status === 'paused' && (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction(() => subscriptionsApi.resumeSubscription(sub.id))}
                className="px-3 py-1.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg font-medium inline-flex items-center space-x-1"
              >
                <PlayCircle className="w-3.5 h-3.5" />
                <span>Resume</span>
              </button>
            )}
            {sub.status !== 'cancelled' && sub.status !== 'archived' && (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction(() => subscriptionsApi.cancelSubscription(sub.id))}
                className="px-3 py-1.5 bg-rose-50 text-rose-700 border border-rose-200 rounded-lg font-medium inline-flex items-center space-x-1"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Cancel</span>
              </button>
            )}
            {sub.status !== 'archived' && (
              <>
                <button
                  type="button"
                  onClick={() => onEdit(sub)}
                  className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-lg font-medium"
                >
                  Edit
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => runAction(() => subscriptionsApi.archiveSubscription(sub.id))}
                  className="px-3 py-1.5 bg-gray-50 hover:bg-gray-100 text-gray-600 border border-gray-200 rounded-lg font-medium inline-flex items-center space-x-1"
                >
                  <Archive className="w-3.5 h-3.5" />
                  <span>Archive</span>
                </button>
              </>
            )}
          </div>
        </div>

        {err && <div className="p-2.5 bg-red-50 border border-red-200 rounded text-red-700">{err}</div>}

        {/* Metrics Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
          <div>
            <div className="text-gray-500">Current Price</div>
            <div className="font-bold text-gray-900 mt-0.5">
              {sub.amount ? formatINR(sub.amount) : 'Pending / Trial'}
            </div>
          </div>
          <div>
            <div className="text-gray-500">Est. Monthly / Annual</div>
            <div className="font-bold text-indigo-700 mt-0.5">
              {sub.monthly_equivalent
                ? `${formatINR(sub.monthly_equivalent)}/mo`
                : '—'}
            </div>
            {sub.annual_equivalent && (
              <div className="text-[10px] text-gray-500">{formatINR(sub.annual_equivalent)}/yr</div>
            )}
          </div>
          <div>
            <div className="text-gray-500">Next Renewal</div>
            <div className="font-semibold text-gray-900 mt-0.5">
              {sub.next_renewal_date ? formatDate(sub.next_renewal_date) : '—'}
            </div>
          </div>
          <div>
            <div className="text-gray-500">Actual Historical Paid</div>
            <div className="font-bold text-emerald-700 mt-0.5">
              {formatINR(sub.total_actual_paid)}
            </div>
          </div>
        </div>

        {/* Price Change Tracking */}
        {sub.status !== 'archived' && (
          <div className="border border-gray-200 rounded-xl p-3.5 space-y-2.5">
            <div className="font-bold text-gray-800 flex items-center space-x-1.5">
              <TrendingUp className="w-4 h-4 text-indigo-600" />
              <span>Record Price Change (Preserves Past Payments)</span>
            </div>
            <form onSubmit={handlePriceUpdate} className="grid grid-cols-1 sm:grid-cols-4 gap-2">
              <input
                type="number"
                step="0.01"
                min="0.01"
                placeholder="New ₹ Price"
                value={newPrice}
                onChange={(e) => setNewPrice(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded font-mono"
              />
              <input
                type="date"
                value={effDate}
                onChange={(e) => setEffDate(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded"
              />
              <input
                type="text"
                placeholder="Reason (e.g. Plan hike)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded"
              />
              <button
                type="submit"
                disabled={busy}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-semibold"
              >
                Update Price
              </button>
            </form>
            {sub.price_history.length > 0 && (
              <div className="space-y-1 pt-1">
                {sub.price_history.map((h) => (
                  <div key={h.id} className="flex justify-between text-[11px] text-gray-600">
                    <span>
                      {formatDate(h.effective_date)}:{' '}
                      {h.previous_price ? `${formatINR(h.previous_price)} → ` : 'Initial '}
                      <strong>{formatINR(h.new_price)}</strong>
                    </span>
                    <span className="text-gray-400">{h.reason || ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Payment History & Link Existing Transaction */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-bold text-gray-800">
              Payment History ({sub.payments.length})
            </span>
            {sub.status !== 'archived' && (
              <button
                type="button"
                onClick={openLinkTx}
                className="text-blue-600 hover:underline font-medium"
              >
                + Link Existing Expense Transaction
              </button>
            )}
          </div>

          {showLinkTx && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg flex flex-wrap gap-2 items-center">
              <select
                value={selectedTxId}
                onChange={(e) => setSelectedTxId(e.target.value)}
                className="flex-1 min-w-[200px] px-2.5 py-1.5 border border-gray-300 rounded bg-white"
              >
                {recentTxs.map((t) => (
                  <option key={t.id} value={t.id}>
                    {formatDate(t.transaction_date)} — {t.description} ({formatINR(t.amount)})
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() =>
                  selectedTxId &&
                  runAction(() =>
                    subscriptionsApi.linkTransaction(sub.id, {
                      transaction_id: selectedTxId,
                      payment_method: sub.preferred_payment_method || 'upi',
                    })
                  )
                }
                className="px-3 py-1.5 bg-blue-600 text-white rounded font-semibold"
              >
                Link
              </button>
            </div>
          )}

          {sub.payments.length === 0 ? (
            <p className="text-gray-400 py-2">No payments recorded yet.</p>
          ) : (
            <div className="border border-gray-200 rounded-xl divide-y divide-gray-100">
              {sub.payments.map((p) => (
                <div key={p.id} className="p-2.5 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-gray-900">{formatINR(p.amount_paid)}</span>{' '}
                    on {formatDate(p.payment_date)} •{' '}
                    <span className="uppercase">{p.payment_method}</span>
                    {p.payment_status === 'reversed' && (
                      <span className="ml-2 px-1.5 py-0.5 bg-rose-50 text-rose-700 rounded text-[10px] font-bold">
                        REVERSED
                      </span>
                    )}
                  </div>
                  {p.payment_status === 'completed' && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        const r = window.prompt('Reason for reversing this payment:') || '';
                        if (r.trim().length >= 2) {
                          void runAction(() =>
                            subscriptionsApi.reversePayment(sub.id, p.id, r.trim())
                          );
                        }
                      }}
                      className="text-rose-600 hover:underline inline-flex items-center space-x-1 text-[11px]"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Reverse</span>
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
