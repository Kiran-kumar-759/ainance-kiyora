import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AppShell } from '../layouts/AppShell';
import { useSystemStatus } from '../hooks/useSystemStatus';
import { ToastProvider } from '../components/ui/ToastProvider';
import { SkeletonCard } from '../components/ui/Primitives';
import {
  VIEW_DOCUMENT_TITLES,
  getViewFromLocation,
  syncBrowserUrl,
} from '../lib/routes';
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
  const initialRoute = useRef(getViewFromLocation());
  const [currentView, setCurrentView] = useState<string>(initialRoute.current.view);
  const [tokenParam, setTokenParam] = useState<string>(initialRoute.current.token);
  const [txFilters, setTxFilters] = useState<TransactionNavigationFilters | null>(
    initialRoute.current.txFilters
  );
  const [pendingProtectedView, setPendingProtectedView] = useState<string | null>(() =>
    PROTECTED_VIEWS.has(initialRoute.current.view) ? initialRoute.current.view : null
  );
  const didAutoRedirectOnAuthRef = useRef(false);

  const navigateWithUrl = (
    view: string,
    options: { replace?: boolean; nextTxFilters?: TransactionNavigationFilters | null } = {}
  ) => {
    const resolvedFilters =
      view === 'transactions' ? options.nextTxFilters ?? null : null;
    if (view === 'transactions') {
      setTxFilters(resolvedFilters);
    }
    setCurrentView(view);
    syncBrowserUrl(view, {
      replace: options.replace,
      txFilters: resolvedFilters,
    });
    if (typeof window !== 'undefined' && typeof window.scrollTo === 'function') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Keep browser document title aligned with active view
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.title = VIEW_DOCUMENT_TITLES[currentView] || 'FinSight AI';
    }
  }, [currentView]);

  // Listen to browser Back / Forward buttons cleanly
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onPopState = () => {
      const next = getViewFromLocation();
      setTokenParam(next.token);
      setTxFilters(next.txFilters);
      setCurrentView(next.view);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  // When authenticated on login/register/root initial load, steer to requested view or onboarding/dashboard
  useEffect(() => {
    if (!isAuthenticated) {
      didAutoRedirectOnAuthRef.current = false;
      return;
    }
    const onAuthEntry =
      currentView === 'login' ||
      currentView === 'register' ||
      (currentView === 'foundation' && !didAutoRedirectOnAuthRef.current);

    if (onAuthEntry) {
      didAutoRedirectOnAuthRef.current = true;
      if (user && user.onboarding_completed === false) {
        navigateWithUrl('onboarding', { replace: true });
      } else if (pendingProtectedView) {
        const dest = pendingProtectedView;
        setPendingProtectedView(null);
        navigateWithUrl(dest, { replace: true });
      } else {
        const landing = preferences?.notification_preferences?.default_landing_view || 'dashboard';
        navigateWithUrl(String(landing), { replace: true });
      }
    }
  }, [isAuthenticated, currentView, preferences, user, pendingProtectedView]);

  // If unauthenticated on a protected route, remember requested path and redirect cleanly to /login
  useEffect(() => {
    if (!authLoading && !isAuthenticated && PROTECTED_VIEWS.has(currentView)) {
      setPendingProtectedView(currentView);
      navigateWithUrl('login', { replace: true });
    }
  }, [authLoading, isAuthenticated, currentView]);

  const handleNavigate = (view: string, nextTxFilters?: TransactionNavigationFilters) => {
    didAutoRedirectOnAuthRef.current = true;
    navigateWithUrl(view, { nextTxFilters: nextTxFilters || null });
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
              handleNavigate(user && user.onboarding_completed === false ? 'onboarding' : 'dashboard')
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
              handleNavigate('dashboard');
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
