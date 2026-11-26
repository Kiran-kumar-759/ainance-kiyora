import React, { Suspense, lazy, useEffect, useState } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AppShell } from '../layouts/AppShell';
import { useSystemStatus } from '../hooks/useSystemStatus';
import { ToastProvider } from '../components/ui/ToastProvider';
import { SkeletonCard } from '../components/ui/Primitives';
import { LandingPage } from '../pages/landing/LandingPage';
import { LoginPage } from '../pages/auth/LoginPage';
import { RegisterPage } from '../pages/auth/RegisterPage';
import { ForgotPasswordPage } from '../pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/auth/ResetPasswordPage';
import { VerifyEmailPage } from '../pages/auth/VerifyEmailPage';
import { TransactionNavigationFilters } from '../types/analytics';

// Lazy-load rich workspace modules so initial public bundle stays lean
const DashboardPage = lazy(() =>
  import('../pages/finance/DashboardPage').then((m) => ({ default: m.DashboardPage }))
);
const OnboardingWizard = lazy(() =>
  import('../pages/onboarding/OnboardingWizard').then((m) => ({ default: m.OnboardingWizard }))
);
const ProfilePage = lazy(() =>
  import('../pages/profile/ProfilePage').then((m) => ({ default: m.ProfilePage }))
);
const PreferencesPage = lazy(() =>
  import('../pages/settings/PreferencesPage').then((m) => ({ default: m.PreferencesPage }))
);
const SessionsPage = lazy(() =>
  import('../pages/settings/SessionsPage').then((m) => ({ default: m.SessionsPage }))
);
const AccountsPage = lazy(() =>
  import('../pages/finance/AccountsPage').then((m) => ({ default: m.AccountsPage }))
);
const TransactionsPage = lazy(() =>
  import('../pages/finance/TransactionsPage').then((m) => ({ default: m.TransactionsPage }))
);
const TransfersPage = lazy(() =>
  import('../pages/finance/TransfersPage').then((m) => ({ default: m.TransfersPage }))
);
const BankingPage = lazy(() =>
  import('../pages/banking/BankingPage').then((m) => ({ default: m.BankingPage }))
);
const ImportsPage = lazy(() =>
  import('../pages/imports/ImportsPage').then((m) => ({ default: m.ImportsPage }))
);
const AnalyticsPage = lazy(() =>
  import('../pages/analytics/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage }))
);
const ReportsPage = lazy(() =>
  import('../pages/reports/ReportsPage').then((m) => ({ default: m.ReportsPage }))
);
const BillsPage = lazy(() =>
  import('../pages/bills/BillsPage').then((m) => ({ default: m.BillsPage }))
);
const SubscriptionsPage = lazy(() =>
  import('../pages/subscriptions/SubscriptionsPage').then((m) => ({ default: m.SubscriptionsPage }))
);
const LoansPage = lazy(() =>
  import('../pages/loans/LoansPage').then((m) => ({ default: m.LoansPage }))
);
const RemindersPage = lazy(() =>
  import('../pages/reminders/RemindersPage').then((m) => ({ default: m.RemindersPage }))
);
const DocumentsPage = lazy(() =>
  import('../pages/documents/DocumentsPage').then((m) => ({ default: m.DocumentsPage }))
);
const IntegrationsPage = lazy(() =>
  import('../pages/integrations/IntegrationsPage').then((m) => ({ default: m.IntegrationsPage }))
);
const IntelligencePage = lazy(() =>
  import('../pages/intelligence/IntelligencePage').then((m) => ({ default: m.IntelligencePage }))
);
const ForecastingPage = lazy(() =>
  import('../pages/forecasting/ForecastingPage').then((m) => ({ default: m.ForecastingPage }))
);
const AssistantPage = lazy(() =>
  import('../pages/assistant/AssistantPage').then((m) => ({ default: m.AssistantPage }))
);
const SettingsPage = lazy(() =>
  import('../pages/settings/SettingsPage').then((m) => ({ default: m.SettingsPage }))
);

const PROTECTED_VIEWS = new Set([
  'dashboard',
  'accounts',
  'transactions',
  'transfers',
  'banking',
  'imports',
  'analytics',
  'reports',
  'bills',
  'subscriptions',
  'loans',
  'reminders',
  'documents',
  'integrations',
  'intelligence',
  'forecasting',
  'assistant',
  'profile',
  'preferences',
  'sessions',
  'settings',
  'onboarding',
]);

const PUBLIC_STANDALONE_VIEWS = new Set([
  'foundation',
  'login',
  'register',
  'forgot-password',
  'reset-password',
  'verify-email',
]);

const ViewLoader: React.FC = () => (
  <div className="space-y-4 py-2">
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <SkeletonCard rows={2} />
      <SkeletonCard rows={2} />
      <SkeletonCard rows={2} />
      <SkeletonCard rows={2} />
    </div>
    <SkeletonCard rows={4} />
  </div>
);

const AppContent: React.FC = () => {
  const {
    health,
    readiness,
    platform,
    isLoading: statusLoading,
    error: statusError,
    backendReachable,
    databaseReady,
    refresh,
  } = useSystemStatus();

  const { user, preferences, isAuthenticated, isLoading: authLoading } = useAuth();
  const [currentView, setCurrentView] = useState<string>('foundation');
  const [tokenParam, setTokenParam] = useState<string>('');
  const [txFilters, setTxFilters] = useState<TransactionNavigationFilters | null>(null);

  // When authenticated on login/register/initial load, route to onboarding (if incomplete) or landing view
  useEffect(() => {
    if (isAuthenticated && (currentView === 'foundation' || currentView === 'login' || currentView === 'register')) {
      if (user && user.onboarding_completed === false) {
        setCurrentView('onboarding');
      } else {
        const landing = preferences?.notification_preferences?.default_landing_view || 'dashboard';
        setCurrentView(String(landing));
      }
    }
  }, [isAuthenticated, currentView, preferences, user]);

  // If session expires or user logs out while on a protected view, steer gracefully to login
  useEffect(() => {
    if (!authLoading && !isAuthenticated && PROTECTED_VIEWS.has(currentView)) {
      setCurrentView('login');
    }
  }, [authLoading, isAuthenticated, currentView]);

  // Check URL parameters for email verification or password reset tokens
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const token = urlParams.get('token');
      const action = urlParams.get('action');

      if (token) {
        setTokenParam(token);
        if (action === 'reset-password' || window.location.pathname.includes('reset-password')) {
          setCurrentView('reset-password');
        } else {
          setCurrentView('verify-email');
        }
      }
    }
  }, []);

  const handleNavigate = (view: string, nextTxFilters?: TransactionNavigationFilters) => {
    if (view === 'transactions') {
      setTxFilters(nextTxFilters || null);
    }
    setCurrentView(view);
  };

  const renderContent = () => {
    switch (currentView) {
      case 'dashboard':
        return <DashboardPage onNavigate={handleNavigate} userName={user?.full_name} />;
      case 'accounts':
        return <AccountsPage onNavigate={handleNavigate} />;
      case 'transactions':
        return <TransactionsPage onNavigate={handleNavigate} initialFilters={txFilters} />;
      case 'transfers':
        return <TransfersPage onNavigate={handleNavigate} />;
      case 'banking':
        return <BankingPage onNavigate={handleNavigate} />;
      case 'imports':
        return <ImportsPage onNavigate={handleNavigate} />;
      case 'analytics':
        return <AnalyticsPage onNavigate={handleNavigate} />;
      case 'reports':
        return <ReportsPage onNavigate={handleNavigate} />;
      case 'bills':
        return <BillsPage onNavigate={handleNavigate} />;
      case 'subscriptions':
        return <SubscriptionsPage onNavigate={handleNavigate} />;
      case 'loans':
        return <LoansPage onNavigate={handleNavigate} />;
      case 'reminders':
        return <RemindersPage onNavigate={handleNavigate} />;
      case 'documents':
        return <DocumentsPage onNavigate={handleNavigate} />;
      case 'integrations':
        return <IntegrationsPage onNavigate={handleNavigate} />;
      case 'intelligence':
        return <IntelligencePage onNavigate={handleNavigate} />;
      case 'forecasting':
        return <ForecastingPage onNavigate={handleNavigate} />;
      case 'assistant':
        return <AssistantPage onNavigate={handleNavigate} />;
      case 'settings':
        return <SettingsPage onNavigate={handleNavigate} />;
      case 'login':
        return (
          <LoginPage
            onNavigate={handleNavigate}
            onSuccess={() =>
              setCurrentView(user && user.onboarding_completed === false ? 'onboarding' : 'dashboard')
            }
          />
        );
      case 'register':
        return <RegisterPage onNavigate={handleNavigate} />;
      case 'forgot-password':
        return <ForgotPasswordPage onNavigate={handleNavigate} />;
      case 'reset-password':
        return <ResetPasswordPage token={tokenParam} onNavigate={handleNavigate} />;
      case 'verify-email':
        return <VerifyEmailPage token={tokenParam} onNavigate={handleNavigate} />;
      case 'onboarding':
        return (
          <OnboardingWizard
            onComplete={() => {
              setCurrentView('dashboard');
            }}
          />
        );
      case 'profile':
        return <ProfilePage onNavigate={handleNavigate} />;
      case 'preferences':
        return <PreferencesPage onNavigate={handleNavigate} />;
      case 'sessions':
        return <SessionsPage onNavigate={handleNavigate} />;
      case 'foundation':
      default:
        return (
          <LandingPage
            health={health}
            readiness={readiness}
            platform={platform}
            isLoading={statusLoading}
            error={statusError}
            onRefresh={refresh}
            onNavigate={handleNavigate}
            isAuthenticated={isAuthenticated}
          />
        );
    }
  };

  // Full-bleed Landing and Standalone Auth Screens without AppShell chrome
  if (PUBLIC_STANDALONE_VIEWS.has(currentView)) {
    return (
      <div className="min-h-screen bg-slate-50">
        {renderContent()}
      </div>
    );
  }

  return (
    <AppShell
      backendReachable={backendReachable}
      databaseReady={databaseReady}
      isLoading={statusLoading || authLoading}
      onRefresh={refresh}
      currentView={currentView}
      onNavigate={handleNavigate}
    >
      <Suspense fallback={<ViewLoader />}>{renderContent()}</Suspense>
    </AppShell>
  );
};

export const App: React.FC = () => {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ToastProvider>
  );
};

export default App;
