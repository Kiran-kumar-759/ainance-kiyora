import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Bell,
  Check,
  CheckCircle2,
  FastForward,
  FileSpreadsheet,
  FolderOpen,
  Landmark,
  Loader2,
  RefreshCw,
  Sparkles,
  Upload,
  User,
  Wallet,
} from 'lucide-react';
import { BankCatalogSelector } from '../../components/banking/BankCatalogSelector';
import { useAuth } from '../../context/AuthContext';
import { formatINR } from '../../lib/formatters';
import { authApi } from '../../services/authApi';
import { documentsApi } from '../../services/documentsApi';
import { financeApi } from '../../services/financeApi';
import { importsApi } from '../../services/importsApi';
import { InitializationStepStatus, UserPreferences } from '../../types/auth';
import { DocumentCategory } from '../../types/documents';
import {
  AccountType,
  BankInstitution,
  BankingConnection,
  DiscoveredAccount,
  FinancialAccount,
} from '../../types/finance';

interface OnboardingWizardProps {
  onComplete: (nextView?: string) => void;
  onNavigate?: (view: string) => void;
}

type SetupMethodTab =
  | 'bank_connect'
  | 'manual_account'
  | 'statement_import'
  | 'document_upload'
  | 'skip';

const GOAL_OPTIONS = [
  'Emergency Fund',
  'Monthly Budget Control',
  'Debt / EMI Payoff',
  'SIP & Investments',
  'Tax Planning',
];

export const OnboardingWizard: React.FC<OnboardingWizardProps> = ({
  onComplete,
  onNavigate,
}) => {
  const { user, preferences, refreshUser } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [postOnboardingDestination, setPostOnboardingDestination] = useState<string>('dashboard');

  // Step 2: Profile + Regional
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [phoneNumber, setPhoneNumber] = useState(
    String(preferences?.notification_preferences?.phone_number || '')
  );
  const [currency, setCurrency] = useState(preferences?.preferred_currency || 'INR');
  const [locale, setLocale] = useState(preferences?.locale || 'en-IN');
  const [timezone, setTimezone] = useState(preferences?.timezone || 'Asia/Kolkata');
  const [dateFormat, setDateFormat] = useState(preferences?.date_format || 'DD/MM/YYYY');
  const [monthlyBudget, setMonthlyBudget] = useState('');
  const [incomeRange, setIncomeRange] = useState('');
  const [financialGoals, setFinancialGoals] = useState<string[]>(['Emergency Fund']);

  // Step 3: Notifications
  const [emailAlerts, setEmailAlerts] = useState(
    preferences?.notification_preferences?.email_alerts ?? true
  );
  const [billReminders, setBillReminders] = useState(
    preferences?.notification_preferences?.bill_reminders ?? true
  );
  const [monthlySummary, setMonthlySummary] = useState(
    preferences?.notification_preferences?.monthly_summary ?? true
  );

  // Step 4: Financial Setup Orchestration
  const [setupMethod, setSetupMethod] = useState<SetupMethodTab>('bank_connect');
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [setupSuccessNote, setSetupSuccessNote] = useState<string | null>(null);

  // Method A: Bank Connect
  const [selectedInstitution, setSelectedInstitution] = useState<BankInstitution | null>(null);
  const [activeConn, setActiveConn] = useState<BankingConnection | null>(null);
  const [discoveredAccounts, setDiscoveredAccounts] = useState<DiscoveredAccount[]>([]);
  const [selectedExternalIds, setSelectedExternalIds] = useState<string[]>([]);
  const [bankingBusy, setBankingBusy] = useState(false);

  // Method B: Manual Account
  const [manualName, setManualName] = useState('');
  const [manualType, setManualType] = useState<AccountType>('savings');
  const [manualInstitution, setManualInstitution] = useState('');
  const [manualOpeningBalance, setManualOpeningBalance] = useState('0.00');
  const [manualBusy, setManualBusy] = useState(false);

  // Method C: Statement Import
  const [importAccountId, setImportAccountId] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importBusy, setImportBusy] = useState(false);

  // Method D: Document Upload
  const [docCategory, setDocCategory] = useState<DocumentCategory>('electricity_bill');
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docBusy, setDocBusy] = useState(false);

  // Step 5: Workspace Initialization
  const [initStatus, setInitStatus] = useState<
    'not_started' | 'in_progress' | 'completed' | 'failed'
  >('not_started');
  const [initSteps, setInitSteps] = useState<InitializationStepStatus[]>([]);
  const [initError, setInitError] = useState<string | null>(null);
  const [initBusy, setInitBusy] = useState(false);

  useEffect(() => {
    const restore = async () => {
      try {
        if (typeof authApi.getComprehensiveOnboardingStatus === 'function') {
          const comp = await authApi.getComprehensiveOnboardingStatus();
          if (comp && !comp.onboarding_completed) {
            if (comp.current_step && comp.current_step >= 1 && comp.current_step <= 5) {
              setCurrentStep(comp.current_step);
            } else if (comp.current_stage === 'financial_data_setup') {
              setCurrentStep(4);
            } else if (comp.current_stage === 'data_processing') {
              setCurrentStep(5);
            }
            if (comp.profile?.phone_number) setPhoneNumber(comp.profile.phone_number);
            if (comp.profile?.monthly_budget) setMonthlyBudget(String(comp.profile.monthly_budget));
            if (comp.profile?.monthly_income_range) setIncomeRange(comp.profile.monthly_income_range);
            if (comp.profile?.financial_goals?.length) setFinancialGoals(comp.profile.financial_goals);
            if (comp.initialization_status) setInitStatus(comp.initialization_status);
            if (comp.initialization_steps?.length) setInitSteps(comp.initialization_steps);
            if (comp.initialization_error) setInitError(comp.initialization_error);
            if (comp.selected_setup_method) {
              setSetupMethod(comp.selected_setup_method as SetupMethodTab);
            }
          }
        } else {
          const status = await authApi.getOnboarding();
          if (status?.current_step && !status.onboarding_completed) {
            setCurrentStep(status.current_step);
          }
        }
      } catch {
        // Ignore if unmocked in isolated tests
      }
      try {
        const accList = await financeApi.listAccounts(false);
        setAccounts(accList);
        if (accList.length > 0) setImportAccountId(accList[0].id);
      } catch {
        // Ignore
      }
    };
    void restore();
  }, []);

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
        if (preferences.notification_preferences.phone_number) {
          setPhoneNumber(String(preferences.notification_preferences.phone_number));
        }
      }
    }
  }, [user, preferences]);

  const refreshAccounts = async () => {
    try {
      const list = await financeApi.listAccounts(false);
      setAccounts(list);
      if (list.length > 0 && !importAccountId) setImportAccountId(list[0].id);
    } catch {
      // ignore
    }
  };

  const persistProgress = async (nextStep: number) => {
    if (nextStep === 3 && typeof authApi.saveOnboardingProfile === 'function') {
      const parts = fullName.trim().split(/\s+/);
      await authApi.saveOnboardingProfile({
        first_name: parts[0] || undefined,
        last_name: parts.slice(1).join(' ') || undefined,
        full_name: fullName.trim() || undefined,
        phone_number: phoneNumber.trim() || undefined,
        preferred_currency: currency,
        locale,
        timezone,
        date_format: dateFormat,
        monthly_budget: monthlyBudget.trim() || undefined,
        monthly_income_range: incomeRange || undefined,
        financial_goals: financialGoals,
        notification_preferences: {
          email_alerts: emailAlerts,
          bill_reminders: billReminders,
          monthly_summary: monthlySummary,
        },
      });
    }
    const patchData: Partial<UserPreferences> & { full_name?: string; current_step?: number } = {
      full_name: fullName,
      current_step: nextStep,
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

  const runInitialization = async (force: boolean = false) => {
    setInitBusy(true);
    setInitError(null);
    try {
      if (typeof authApi.initializeWorkspace === 'function') {
        const res = force
          ? await authApi.retryWorkspaceInitialization()
          : await authApi.initializeWorkspace(false);
        setInitStatus(res.initialization_status);
        setInitSteps(res.steps || []);
        setInitError(res.initialization_error || null);
        await refreshUser();
      } else {
        await authApi.completeOnboarding();
        await refreshUser();
        setInitStatus('completed');
      }
    } catch (err: unknown) {
      setInitStatus('failed');
      setInitError(
        err instanceof Error ? err.message : 'Workspace initialization failed. Please retry.'
      );
      try {
        if (typeof authApi.getInitializationStatus === 'function') {
          const st = await authApi.getInitializationStatus();
          setInitSteps(st.steps || []);
        }
      } catch {
        // ignore
      }
    } finally {
      setInitBusy(false);
    }
  };

  const handleNext = async () => {
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      if (currentStep < 5) {
        const nextStep = currentStep + 1;
        await persistProgress(nextStep);
        setCurrentStep(nextStep);
        if (nextStep === 5) {
          await runInitialization(false);
        }
      } else {
        await refreshUser();
        const dest = postOnboardingDestination || 'dashboard';
        if (onNavigate && dest !== 'dashboard') {
          onNavigate(dest);
        } else {
          onComplete(dest);
        }
      }
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to save onboarding progress.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBack = () => {
    setErrorMessage(null);
    if (currentStep > 1) setCurrentStep((p) => p - 1);
  };

  const handleSkipAll = async () => {
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      if (typeof authApi.skipFinancialSetup === 'function') {
        await authApi.skipFinancialSetup(true, 'Skipped during onboarding wizard');
      } else {
        await authApi.skipOnboarding();
      }
      await refreshUser();
      onComplete('dashboard');
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to skip onboarding.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleInitiateDemoBank = async () => {
    if (!selectedInstitution || !selectedInstitution.is_demo) return;
    setBankingBusy(true);
    setErrorMessage(null);
    setSetupSuccessNote(null);
    try {
      if (typeof authApi.selectFinancialSetupMethod === 'function') {
        await authApi.selectFinancialSetupMethod('bank_connect', selectedInstitution.bank_id);
      }
      const conn = await financeApi.initiateBankingConnection(
        selectedInstitution.bank_id,
        'demo',
        false
      );
      setActiveConn(conn);
      setDiscoveredAccounts([]);
      setSelectedExternalIds([]);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to initiate connection.');
    } finally {
      setBankingBusy(false);
    }
  };

  const handleGrantConsentAndDiscover = async () => {
    if (!activeConn) return;
    setBankingBusy(true);
    setErrorMessage(null);
    try {
      const consented = await financeApi.submitBankingConsent(activeConn.id, true);
      setActiveConn(consented);
      const discovered = await financeApi.discoverBankingAccounts(consented.id);
      setDiscoveredAccounts(discovered);
      setSelectedExternalIds(
        discovered.filter((a) => !a.already_imported).map((a) => a.external_account_id)
      );
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Consent or discovery failed.');
    } finally {
      setBankingBusy(false);
    }
  };

  const handleImportDiscoveredAccounts = async () => {
    if (!activeConn || selectedExternalIds.length === 0) return;
    setBankingBusy(true);
    setErrorMessage(null);
    try {
      const imported = await financeApi.importBankingAccounts(
        activeConn.id,
        selectedExternalIds,
        true
      );
      await refreshAccounts();
      setSetupSuccessNote(
        `Connected ${activeConn.institution_name} and synchronized ${imported.length} account(s) with transactions.`
      );
      setDiscoveredAccounts([]);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to import bank accounts.');
    } finally {
      setBankingBusy(false);
    }
  };

  const handleCreateManualAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualName.trim()) {
      setErrorMessage('Enter an account name.');
      return;
    }
    setManualBusy(true);
    setErrorMessage(null);
    setSetupSuccessNote(null);
    try {
      if (typeof authApi.selectFinancialSetupMethod === 'function') {
        await authApi.selectFinancialSetupMethod('manual_account');
      }
      const created = await financeApi.createAccount({
        name: manualName.trim(),
        account_type: manualType,
        institution_name: manualInstitution.trim() || null,
        opening_balance: manualOpeningBalance.trim() || '0.00',
        currency: 'INR',
      });
      await refreshAccounts();
      setImportAccountId(created.id);
      setManualName('');
      setSetupSuccessNote(
        `Account "${created.name}" created with opening balance ${formatINR(created.current_balance)}.`
      );
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to create account.');
    } finally {
      setManualBusy(false);
    }
  };

  const handleUploadStatement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importAccountId || !importFile) {
      setErrorMessage('Select a destination account and CSV/XLSX statement file.');
      return;
    }
    setImportBusy(true);
    setErrorMessage(null);
    setSetupSuccessNote(null);
    try {
      if (typeof authApi.selectFinancialSetupMethod === 'function') {
        await authApi.selectFinancialSetupMethod('statement_import');
      }
      const res = await importsApi.uploadStatement(importAccountId, importFile);
      setPostOnboardingDestination('imports');
      setSetupSuccessNote(
        `Uploaded "${res.batch.original_filename}" (${res.batch.total_rows} rows staged). Complete column mapping right after initialization.`
      );
      setImportFile(null);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to upload statement.');
    } finally {
      setImportBusy(false);
    }
  };

  const handleUploadDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docFile) {
      setErrorMessage('Choose a PDF or image receipt/bill to upload.');
      return;
    }
    setDocBusy(true);
    setErrorMessage(null);
    setSetupSuccessNote(null);
    try {
      if (typeof authApi.selectFinancialSetupMethod === 'function') {
        await authApi.selectFinancialSetupMethod('document_upload');
      }
      const doc = await documentsApi.uploadDocument(docFile, docCategory, true);
      setPostOnboardingDestination('documents');
      setSetupSuccessNote(
        `Uploaded "${doc.original_filename}" cleanly for private OCR extraction & review.`
      );
      setDocFile(null);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Document upload failed.');
    } finally {
      setDocBusy(false);
    }
  };

  const handleSkipFinancialSetupOnly = async () => {
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      if (typeof authApi.skipFinancialSetup === 'function') {
        await authApi.skipFinancialSetup(false, 'User chose to skip financial setup');
      }
      setSetupSuccessNote(
        'Financial data setup skipped. You can connect banks or upload statements anytime from the workspace.'
      );
      setCurrentStep(5);
      await runInitialization(false);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Unable to skip financial setup.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleGoal = (goal: string) => {
    setFinancialGoals((prev) =>
      prev.includes(goal) ? prev.filter((g) => g !== goal) : [...prev, goal]
    );
  };

  const steps = [
    { num: 1, title: 'Welcome', icon: Sparkles },
    { num: 2, title: 'Profile', icon: User },
    { num: 3, title: 'Alerts', icon: Bell },
    { num: 4, title: 'Financial Setup', icon: Landmark },
    { num: 5, title: 'Ready', icon: CheckCircle2 },
  ];

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      {/* Progress Stepper */}
      <div className="mb-8">
        <div className="flex items-center justify-between relative">
          <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-slate-200 -translate-y-1/2 z-0" />
          <div
            className="absolute top-1/2 left-0 h-0.5 bg-indigo-600 -translate-y-1/2 z-0 transition-all duration-300"
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
                      ? 'bg-indigo-600 border-indigo-600 text-white'
                      : isCurrent
                      ? 'bg-white border-indigo-600 text-indigo-600 shadow-sm'
                      : 'bg-white border-slate-300 text-slate-400'
                  }`}
                >
                  {isDone ? <Check className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                </div>
                <span
                  className={`text-[11px] font-medium mt-1.5 hidden sm:block ${
                    isCurrent ? 'text-indigo-700 font-semibold' : 'text-slate-500'
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
          <div className="mb-5 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
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
              Designed specifically for individuals in India. Configure your profile, connect a bank
              or import statements, and activate your real-data financial dashboard.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3">
              <div className="p-3 bg-slate-50 border border-slate-200/70 rounded-xl text-xs">
                <div className="font-semibold text-slate-800 mb-1">🇮🇳 India-First Architecture</div>
                <p className="text-slate-500 text-[11px]">
                  INR defaults, Lakhs/Crores formatting, Asia/Kolkata timezone, and April–March FY.
                </p>
              </div>
              <div className="p-3 bg-slate-50 border border-slate-200/70 rounded-xl text-xs">
                <div className="font-semibold text-slate-800 mb-1">🔒 Real Data Only</div>
                <p className="text-slate-500 text-[11px]">
                  Strict tenant isolation and zero fabricated accounts or dummy balances.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Profile & Preferences */}
        {currentStep === 2 && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Confirm Your Profile</h2>
            <p className="text-xs text-slate-500">
              Set your identity, regional defaults (India / INR), and optional budget goals.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  placeholder="e.g. Aarav Mehta"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Phone Number (Optional)
                </label>
                <input
                  type="tel"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  placeholder="+91 9876543210"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Currency</label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white"
                >
                  <option value="INR">INR (₹) — Indian Rupee</option>
                  <option value="USD">USD ($) — US Dollar</option>
                  <option value="EUR">EUR (€) — Euro</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Timezone &amp; Format</label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white"
                >
                  <option value="Asia/Kolkata">Asia/Kolkata (IST) • DD/MM/YYYY</option>
                  <option value="UTC">UTC (+00:00)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Monthly Spending Target (Optional, ₹)
                </label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={monthlyBudget}
                  onChange={(e) => setMonthlyBudget(e.target.value)}
                  placeholder="e.g. 45000"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Monthly Income Range (Optional)
                </label>
                <select
                  value={incomeRange}
                  onChange={(e) => setIncomeRange(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white"
                >
                  <option value="">Prefer not to say</option>
                  <option value="below-50k">Below ₹50,000</option>
                  <option value="50k-100k">₹50,000 – ₹1,00,000</option>
                  <option value="100k-250k">₹1,00,000 – ₹2,50,000</option>
                  <option value="above-250k">Above ₹2,50,000</option>
                </select>
              </div>
            </div>
            <div>
              <span className="block text-xs font-medium text-slate-700 mb-1.5">
                Financial Goals (Optional)
              </span>
              <div className="flex flex-wrap gap-1.5">
                {GOAL_OPTIONS.map((goal) => {
                  const active = financialGoals.includes(goal);
                  return (
                    <button
                      key={goal}
                      type="button"
                      onClick={() => toggleGoal(goal)}
                      className={`px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors ${
                        active
                          ? 'bg-indigo-600 text-white border-indigo-600'
                          : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {goal}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Alerts */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Notifications &amp; Alerts
            </h2>
            <p className="text-xs text-slate-500">
              Choose which reminders and financial summaries you want enabled.
            </p>
            <div className="space-y-3 pt-1">
              {[
                {
                  title: 'Security & Email Alerts',
                  desc: 'Login alerts, password updates, and verification notices',
                  checked: emailAlerts,
                  onChange: setEmailAlerts,
                },
                {
                  title: 'Bill, Subscription & EMI Reminders',
                  desc: 'Upcoming bill due dates, OTT renewals, and EMI alerts',
                  checked: billReminders,
                  onChange: setBillReminders,
                },
                {
                  title: 'Monthly Spending Summary',
                  desc: 'Period cashflow breakdown and AI insights summary',
                  checked: monthlySummary,
                  onChange: setMonthlySummary,
                },
              ].map((item) => (
                <label
                  key={item.title}
                  className="flex items-center justify-between p-3 border border-slate-200 rounded-xl hover:bg-slate-50 cursor-pointer"
                >
                  <div>
                    <div className="text-xs font-semibold text-slate-800">{item.title}</div>
                    <div className="text-[11px] text-slate-500">{item.desc}</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={item.checked}
                    onChange={(e) => item.onChange(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Step 4: Financial Data Setup Orchestration */}
        {currentStep === 4 && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                  Set Up Your Financial Data
                </h2>
                <p className="text-xs text-slate-500">
                  Choose any method below, or skip and populate your workspace later.
                </p>
              </div>
              {accounts.length > 0 && (
                <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold self-start">
                  {accounts.length} active account(s) ready
                </span>
              )}
            </div>

            {setupSuccessNote && (
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{setupSuccessNote}</span>
              </div>
            )}

            {/* Setup Method Selector Pills */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {[
                { id: 'bank_connect', label: 'Connect Bank', icon: Landmark },
                { id: 'manual_account', label: 'Add Account', icon: Wallet },
                { id: 'statement_import', label: 'Import CSV/XLSX', icon: FileSpreadsheet },
                { id: 'document_upload', label: 'Upload Receipt', icon: FolderOpen },
                { id: 'skip', label: 'Skip for Now', icon: FastForward },
              ].map((m) => {
                const Icon = m.icon;
                const active = setupMethod === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => {
                      setSetupMethod(m.id as SetupMethodTab);
                      setErrorMessage(null);
                    }}
                    className={`p-2.5 rounded-xl border text-left transition-all ${
                      active
                        ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                        : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    <Icon className="w-4 h-4 mb-1" />
                    <div className="text-[11px] font-semibold leading-tight">{m.label}</div>
                  </button>
                );
              })}
            </div>

            {/* Method A: Bank Catalog & Connection Lifecycle */}
            {setupMethod === 'bank_connect' && (
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-4">
                <BankCatalogSelector
                  selectedBankId={selectedInstitution?.bank_id}
                  onSelectInstitution={(inst) => {
                    setSelectedInstitution(inst);
                    setActiveConn(null);
                    setDiscoveredAccounts([]);
                  }}
                  onChooseManualAccount={(instName) => {
                    setManualInstitution(instName);
                    setManualName(`${instName} Savings`);
                    setSetupMethod('manual_account');
                  }}
                  onChooseStatementImport={() => setSetupMethod('statement_import')}
                />

                {selectedInstitution?.is_demo && !activeConn && (
                  <button
                    type="button"
                    disabled={bankingBusy}
                    onClick={handleInitiateDemoBank}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold disabled:opacity-50"
                  >
                    {bankingBusy ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Landmark className="w-3.5 h-3.5" />
                    )}
                    <span>Initiate Demo Connection ({selectedInstitution.short_name})</span>
                  </button>
                )}

                {activeConn && discoveredAccounts.length === 0 && activeConn.status !== 'connected' && (
                  <div className="p-3.5 rounded-xl bg-white border border-indigo-200 space-y-2.5 text-xs">
                    <div className="font-semibold text-slate-900">
                      Read-Only Consent Confirmation — {activeConn.institution_name}
                    </div>
                    <p className="text-[11px] text-slate-600">
                      Grant explicit read-only demo consent to discover accounts and transactions. No
                      banking passwords, PINs, or OTPs are ever requested.
                    </p>
                    <button
                      type="button"
                      disabled={bankingBusy}
                      onClick={handleGrantConsentAndDiscover}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold disabled:opacity-50"
                    >
                      {bankingBusy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>Grant Consent &amp; Discover Accounts</span>
                    </button>
                  </div>
                )}

                {activeConn && discoveredAccounts.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-white border border-slate-200 space-y-3 text-xs">
                    <div className="font-semibold text-slate-900">
                      Select Accounts to Import ({discoveredAccounts.length} discovered)
                    </div>
                    <div className="space-y-2">
                      {discoveredAccounts.map((acc) => {
                        const checked = selectedExternalIds.includes(acc.external_account_id);
                        return (
                          <label
                            key={acc.external_account_id}
                            className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 cursor-pointer hover:bg-slate-50"
                          >
                            <div className="flex items-center gap-2.5">
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={acc.already_imported}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedExternalIds((p) => [...p, acc.external_account_id]);
                                  } else {
                                    setSelectedExternalIds((p) =>
                                      p.filter((id) => id !== acc.external_account_id)
                                    );
                                  }
                                }}
                                className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                              />
                              <div>
                                <div className="font-semibold text-slate-900">{acc.name}</div>
                                <div className="text-[11px] text-slate-500">
                                  {acc.account_type.replace('_', ' ').toUpperCase()} &bull;{' '}
                                  {acc.masked_account_number}
                                </div>
                              </div>
                            </div>
                            <span className="font-bold text-slate-900">
                              {formatINR(acc.balance)}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                    <button
                      type="button"
                      disabled={bankingBusy || selectedExternalIds.length === 0}
                      onClick={handleImportDiscoveredAccounts}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold disabled:opacity-50"
                    >
                      {bankingBusy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>Import Selected &amp; Sync Transactions</span>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Method B: Manual Account Creation */}
            {setupMethod === 'manual_account' && (
              <form
                onSubmit={handleCreateManualAccount}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-3 text-xs"
              >
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Account Name *</label>
                    <input
                      type="text"
                      required
                      value={manualName}
                      onChange={(e) => setManualName(e.target.value)}
                      placeholder="e.g. HDFC Salary Savings"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Account Type *</label>
                    <select
                      value={manualType}
                      onChange={(e) => setManualType(e.target.value as AccountType)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white"
                    >
                      <option value="savings">Savings Account</option>
                      <option value="current">Current Account</option>
                      <option value="cash">Cash Account</option>
                      <option value="credit_card">Credit Card</option>
                      <option value="digital_wallet">Digital Wallet</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      Bank / Institution (Optional)
                    </label>
                    <input
                      type="text"
                      value={manualInstitution}
                      onChange={(e) => setManualInstitution(e.target.value)}
                      placeholder="e.g. HDFC Bank, SBI"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      Opening Balance (₹)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={manualOpeningBalance}
                      onChange={(e) => setManualOpeningBalance(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white font-mono"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={manualBusy}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold disabled:opacity-50"
                >
                  {manualBusy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Create Account</span>
                </button>
              </form>
            )}

            {/* Method C: Statement Import */}
            {setupMethod === 'statement_import' && (
              <form
                onSubmit={handleUploadStatement}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-3 text-xs"
              >
                {accounts.length === 0 ? (
                  <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900">
                    Create a destination account first before uploading a statement.{' '}
                    <button
                      type="button"
                      onClick={() => setSetupMethod('manual_account')}
                      className="font-semibold underline"
                    >
                      Add Account Manually &rarr;
                    </button>
                  </div>
                ) : (
                  <>
                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">
                        Destination Account *
                      </label>
                      <select
                        value={importAccountId}
                        onChange={(e) => setImportAccountId(e.target.value)}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white"
                      >
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name} ({formatINR(a.current_balance)})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">
                        CSV / XLSX Bank Statement *
                      </label>
                      <input
                        type="file"
                        accept=".csv,.xlsx"
                        onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                        className="w-full text-xs text-slate-600"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={importBusy || !importFile}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold disabled:opacity-50"
                    >
                      {importBusy ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Upload className="w-3.5 h-3.5" />
                      )}
                      <span>Upload Statement</span>
                    </button>
                  </>
                )}
              </form>
            )}

            {/* Method D: Upload Bill / Receipt */}
            {setupMethod === 'document_upload' && (
              <form
                onSubmit={handleUploadDocument}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-3 text-xs"
              >
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      Document Category
                    </label>
                    <select
                      value={docCategory}
                      onChange={(e) => setDocCategory(e.target.value as DocumentCategory)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white"
                    >
                      <option value="electricity_bill">Electricity Bill</option>
                      <option value="internet_bill">Internet &amp; Broadband</option>
                      <option value="shopping_receipt">Shopping Receipt</option>
                      <option value="credit_card_statement">Credit Card Statement</option>
                      <option value="other">Other Financial Document</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      PDF, PNG, JPG, or WebP File
                    </label>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,.webp"
                      onChange={(e) => setDocFile(e.target.files?.[0] || null)}
                      className="w-full text-xs text-slate-600"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={docBusy || !docFile}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold disabled:opacity-50"
                >
                  {docBusy ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Upload className="w-3.5 h-3.5" />
                  )}
                  <span>Upload &amp; Queue OCR</span>
                </button>
              </form>
            )}

            {/* Method E: Skip Notice */}
            {setupMethod === 'skip' && (
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3 text-xs">
                <p className="font-semibold text-slate-800">
                  Continue without connecting a bank account right now?
                </p>
                <p className="text-slate-600 leading-relaxed">
                  No dummy accounts or fabricated transactions will be created. Analytics,
                  forecasting, and personalized AI insights will populate automatically once you
                  connect a bank, add an account, or import statements later.
                </p>
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={handleSkipFinancialSetupOnly}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold disabled:opacity-50"
                >
                  <span>Skip Financial Setup &amp; Initialize Workspace</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step 5: Workspace Initialization & Dashboard Activation */}
        {currentStep === 5 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                  {initStatus === 'completed' ? "You're All Set!" : 'Initializing Your Workspace'}
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Preparing your PostgreSQL-backed personal finance workspace with your real records.
                </p>
              </div>
              {initBusy && <Loader2 className="w-5 h-5 animate-spin text-indigo-600 shrink-0" />}
            </div>

            {initError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between gap-3">
                <span>{initError}</span>
                <button
                  type="button"
                  onClick={() => runInitialization(true)}
                  disabled={initBusy}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-rose-600 text-white font-semibold hover:bg-rose-700 shrink-0"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Retry</span>
                </button>
              </div>
            )}

            {initSteps.length > 0 && (
              <div className="space-y-2">
                {initSteps.map((st) => (
                  <div
                    key={st.key}
                    className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-3 text-xs"
                  >
                    <div className="flex items-start gap-2.5">
                      {st.status === 'completed' ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      ) : st.status === 'failed' ? (
                        <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                      ) : (
                        <Loader2 className="w-4 h-4 text-indigo-600 animate-spin shrink-0 mt-0.5" />
                      )}
                      <div>
                        <div className="font-semibold text-slate-900">{st.label}</div>
                        {st.detail && <div className="text-[11px] text-slate-500 mt-0.5">{st.detail}</div>}
                      </div>
                    </div>
                    <span className="text-[10px] uppercase font-bold text-slate-500 shrink-0">
                      {st.status}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {initSteps.length === 0 && !initError && (
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-left text-xs space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-500">Name:</span>
                  <span className="font-medium text-slate-800">{fullName || 'User'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Currency &amp; Timezone:</span>
                  <span className="font-medium text-slate-800">
                    {currency} &bull; {timezone}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Active Accounts:</span>
                  <span className="font-medium text-slate-800">{accounts.length}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer Action Bar */}
        <div className="mt-8 pt-4 border-t border-slate-200/80 flex items-center justify-between">
          <div>
            {currentStep > 1 && initStatus !== 'completed' ? (
              <button
                type="button"
                onClick={handleBack}
                disabled={isSubmitting || initBusy}
                className="inline-flex items-center space-x-1 px-3 py-2 text-xs font-medium text-slate-600 hover:text-slate-900"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back</span>
              </button>
            ) : (
              currentStep < 5 && (
                <button
                  type="button"
                  onClick={handleSkipAll}
                  disabled={isSubmitting}
                  className="inline-flex items-center space-x-1 px-3 py-2 text-xs font-medium text-slate-500 hover:text-slate-800"
                >
                  <FastForward className="w-3.5 h-3.5" />
                  <span>Skip for now</span>
                </button>
              )
            )}
          </div>

          <div className="flex items-center space-x-3">
            {currentStep > 1 && currentStep < 5 && (
              <button
                type="button"
                onClick={handleSkipAll}
                disabled={isSubmitting}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                Skip wizard
              </button>
            )}
            <button
              type="button"
              onClick={handleNext}
              disabled={isSubmitting || initBusy}
              className="inline-flex items-center space-x-1.5 px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition-all shadow-sm"
            >
              <span>
                {currentStep === 5
                  ? postOnboardingDestination !== 'dashboard'
                    ? 'Open Uploaded Flow'
                    : 'Get Started'
                  : 'Continue'}
              </span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
