import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AppShell } from '../layouts/AppShell';
import { SystemStatusView } from '../features/status/SystemStatusView';
import { useSystemStatus } from '../hooks/useSystemStatus';
import { LoginPage } from '../pages/auth/LoginPage';
import { RegisterPage } from '../pages/auth/RegisterPage';
import { ForgotPasswordPage } from '../pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/auth/ResetPasswordPage';
import { VerifyEmailPage } from '../pages/auth/VerifyEmailPage';
import { OnboardingWizard } from '../pages/onboarding/OnboardingWizard';
import { ProfilePage } from '../pages/profile/ProfilePage';
import { PreferencesPage } from '../pages/settings/PreferencesPage';
import { SessionsPage } from '../pages/settings/SessionsPage';
import { DashboardPage } from '../pages/finance/DashboardPage';
import { AccountsPage } from '../pages/finance/AccountsPage';
import { TransactionsPage } from '../pages/finance/TransactionsPage';
import { TransfersPage } from '../pages/finance/TransfersPage';
import { BankingPage } from '../pages/banking/BankingPage';
import { ImportsPage } from '../pages/imports/ImportsPage';
import { AnalyticsPage } from '../pages/analytics/AnalyticsPage';
import { ReportsPage } from '../pages/reports/ReportsPage';
import { BillsPage } from '../pages/bills/BillsPage';
import { SubscriptionsPage } from '../pages/subscriptions/SubscriptionsPage';
import { LoansPage } from '../pages/loans/LoansPage';
import { DocumentsPage } from '../pages/documents/DocumentsPage';
import { IntegrationsPage } from '../pages/integrations/IntegrationsPage';
import { IntelligencePage } from '../pages/intelligence/IntelligencePage';
import { ForecastingPage } from '../pages/forecasting/ForecastingPage';
import { AssistantPage } from '../pages/assistant/AssistantPage';
import { SettingsPage } from '../pages/settings/SettingsPage';
import { TransactionNavigationFilters } from '../types/analytics';

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

const AppContent: React.FC = () => {
  const {
    health,
    readiness,
    platform,
    isLoading: statusLoading,
    error: statusError,
    backendReachable,
    databaseReady,
    lastChecked,
    refresh,
  } = useSystemStatus();

  const { user, preferences, isAuthenticated, isLoading: authLoading } = useAuth();
  const [currentView, setCurrentView] = useState<string>('foundation');
  const [tokenParam, setTokenParam] = useState<string>('');
  const [txFilters, setTxFilters] = useState<TransactionNavigationFilters | null>(null);

  // When user becomes authenticated and is on foundation, steer to configured landing view
  useEffect(() => {
    if (isAuthenticated && currentView === 'foundation') {
      const landing = preferences?.notification_preferences?.default_landing_view || 'dashboard';
      setCurrentView(String(landing));
    }
  }, [isAuthenticated, currentView, preferences]);

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
        return <LoginPage onNavigate={handleNavigate} />;

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
          <SystemStatusView
            health={health}
            readiness={readiness}
            platform={platform}
            isLoading={statusLoading}
            error={statusError}
            backendReachable={backendReachable}
            databaseReady={databaseReady}
            lastChecked={lastChecked}
            onRefresh={refresh}
          />
        );
    }
  };

  return (
    <AppShell
      backendReachable={backendReachable}
      databaseReady={databaseReady}
      isLoading={statusLoading || authLoading}
      onRefresh={refresh}
      currentView={currentView}
      onNavigate={handleNavigate}
    >
      {renderContent()}
    </AppShell>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
