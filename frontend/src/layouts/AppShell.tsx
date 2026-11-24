import React, { useState } from 'react';
import {
  LayoutDashboard,
  BarChart3,
  Wallet,
  Receipt,
  FileSpreadsheet,
  PieChart,
  Target,
  FileText,
  CalendarDays,
  CreditCard,
  Sparkles,
  TrendingUp,
  Bot,
  FolderOpen,
  Plug,
  Settings,
  ShieldCheck,
  Menu,
  X,
  RefreshCw,
  Server,
  Database,
  User as UserIcon,
  LogOut,
  AlertTriangle,
  Sliders,
  Smartphone,
  ChevronRight,
  LogIn,
  UserPlus,
} from 'lucide-react';
import { config } from '../lib/config';
import { Badge } from '../components/common/Badge';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../services/authApi';

interface AppShellProps {
  children: React.ReactNode;
  backendReachable: boolean;
  databaseReady: boolean;
  isLoading: boolean;
  onRefresh: () => void;
  currentView: string;
  onNavigate: (view: string) => void;
}

interface NavSection {
  title: string;
  items: {
    name: string;
    icon: React.ElementType;
    view?: string;
    active?: boolean;
    futurePhase?: string;
  }[];
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  backendReachable,
  databaseReady,
  isLoading,
  onRefresh,
  currentView,
  onNavigate,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const [resendStatus, setResendStatus] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);

  const handleResendVerification = async () => {
    if (!user?.email) return;
    setIsResending(true);
    setResendStatus(null);
    try {
      const res = await authApi.resendVerification(user.email);
      setResendStatus(res.message);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send verification email.';
      setResendStatus(msg);
    } finally {
      setIsResending(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    onNavigate('login');
  };

  const navigationSections: NavSection[] = [
    {
      title: 'Current Foundation',
      items: [
        {
          name: 'System Foundation',
          icon: ShieldCheck,
          view: 'foundation',
          active: currentView === 'foundation',
        },
      ],
    },
    ...(isAuthenticated
      ? [
          {
            title: 'Account & Identity',
            items: [
              {
                name: 'My Profile',
                icon: UserIcon,
                view: 'profile',
                active: currentView === 'profile',
              },
              {
                name: 'Regional Preferences',
                icon: Sliders,
                view: 'preferences',
                active: currentView === 'preferences',
              },
              {
                name: 'Active Sessions',
                icon: Smartphone,
                view: 'sessions',
                active: currentView === 'sessions',
              },
              {
                name: 'Onboarding Wizard',
                icon: Sparkles,
                view: 'onboarding',
                active: currentView === 'onboarding',
              },
            ],
          },
        ]
      : []),
    {
      title: 'Overview',
      items: [
        { name: 'Dashboard', icon: LayoutDashboard, futurePhase: 'Phase 5' },
        { name: 'Analytics', icon: BarChart3, futurePhase: 'Phase 5' },
      ],
    },
    {
      title: 'Money Management',
      items: [
        { name: 'Accounts', icon: Wallet, futurePhase: 'Phase 2' },
        { name: 'Transactions', icon: Receipt, futurePhase: 'Phase 2' },
        { name: 'Imports', icon: FileSpreadsheet, futurePhase: 'Phase 4' },
        { name: 'Budgets', icon: PieChart, futurePhase: 'Phase 6' },
        { name: 'Savings Goals', icon: Target, futurePhase: 'Phase 6' },
      ],
    },
    {
      title: 'Payments & Commitments',
      items: [
        { name: 'Bills', icon: CalendarDays, futurePhase: 'Phase 7' },
        { name: 'Subscriptions', icon: CreditCard, futurePhase: 'Phase 7' },
        { name: 'Loans & EMIs', icon: FileText, futurePhase: 'Phase 8' },
      ],
    },
    {
      title: 'Intelligence',
      items: [
        { name: 'Insights', icon: Sparkles, futurePhase: 'Phase 10' },
        { name: 'Forecasting', icon: TrendingUp, futurePhase: 'Phase 10' },
        { name: 'AI Assistant', icon: Bot, futurePhase: 'Phase 11' },
      ],
    },
    {
      title: 'Documents & Settings',
      items: [
        { name: 'Documents', icon: FolderOpen, futurePhase: 'Phase 9' },
        { name: 'Integrations', icon: Plug, futurePhase: 'Phase 3' },
        { name: 'Settings', icon: Settings, futurePhase: 'Phase 1 Active' },
      ],
    },
  ];

  const sidebarContent = (
    <div className="flex flex-col h-full bg-slate-900 text-slate-300">
      {/* Brand Header */}
      <div className="px-6 py-5 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold text-lg">
            ₹
          </div>
          <div>
            <span className="font-semibold text-white tracking-tight text-sm">
              {config.appTitle}
            </span>
            <div className="text-[10px] text-slate-400 font-mono tracking-wider">
              INDIA SAAS • Phase 1
            </div>
          </div>
        </div>
      </div>

      {/* User Info Tile (if logged in) */}
      {isAuthenticated && user && (
        <div className="px-4 py-3 mx-3 my-2 rounded-xl bg-slate-800/80 border border-slate-700/60 flex items-center justify-between">
          <div className="flex items-center space-x-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-emerald-600/30 border border-emerald-500/40 text-emerald-300 flex items-center justify-center font-bold text-xs flex-shrink-0">
              {user.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-white truncate">{user.full_name}</div>
              <div className="text-[10px] text-slate-400 truncate font-mono">{user.email}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            title="Sign Out"
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-700/60 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5 scrollbar-thin">
        {navigationSections.map((section) => (
          <div key={section.title}>
            <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 mb-1.5">
              {section.title}
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                if (item.view) {
                  return (
                    <button
                      type="button"
                      key={item.name}
                      onClick={() => {
                        onNavigate(item.view!);
                        setMobileMenuOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                        item.active
                          ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/30'
                          : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                      }`}
                    >
                      <div className="flex items-center space-x-2.5">
                        <Icon className={`w-4 h-4 ${item.active ? 'text-emerald-400' : 'text-slate-400'}`} />
                        <span>{item.name}</span>
                      </div>
                      {item.active && (
                        <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                      )}
                    </button>
                  );
                }

                return (
                  <div
                    key={item.name}
                    className="flex items-center justify-between px-3 py-1.5 rounded-lg text-slate-500 text-xs select-none group"
                    title={`Scheduled for ${item.futurePhase}`}
                  >
                    <div className="flex items-center space-x-2.5">
                      <Icon className="w-4 h-4 text-slate-600 group-hover:text-slate-500" />
                      <span>{item.name}</span>
                    </div>
                    {item.futurePhase && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-500 font-mono border border-slate-800">
                        {item.futurePhase}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Sidebar Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40 text-xs">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-slate-400">Environment</span>
          <span className="text-slate-300 font-mono text-[11px] bg-slate-800 px-2 py-0.5 rounded">
            Development
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Active Phase</span>
          <span className="text-emerald-400 font-medium text-[11px]">Phase 1 (Auth)</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block w-72 flex-shrink-0 border-r border-slate-800">
        <div className="fixed top-0 bottom-0 w-72">{sidebarContent}</div>
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative flex-1 flex flex-col max-w-xs w-full bg-slate-900">
            <div className="absolute top-3 right-3">
              <button
                type="button"
                className="p-1.5 rounded-md text-slate-400 hover:text-white"
                onClick={() => setMobileMenuOpen(false)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            {sidebarContent}
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Navbar */}
        <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-sm border-b border-slate-200/80 px-4 sm:px-8 py-3.5 flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-3">
            <button
              type="button"
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-base sm:text-lg font-semibold text-slate-900 tracking-tight">
                  {config.appTitle}
                </h1>
                <Badge variant="info">Phase 1: Auth & User Mgmt</Badge>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                Multi-User SaaS Architecture • India Locale (INR, en-IN, Asia/Kolkata)
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Live Status Indicators */}
            <div className="hidden md:flex items-center space-x-2 text-xs">
              <div
                className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border ${
                  backendReachable
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}
              >
                <Server className="w-3.5 h-3.5" />
                <span>Backend: {backendReachable ? 'Live' : 'Offline'}</span>
              </div>

              <div
                className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border ${
                  databaseReady
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                <span>PostgreSQL: {databaseReady ? 'Ready' : 'Down'}</span>
              </div>
            </div>

            {/* Health check refresh button */}
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-xs disabled:opacity-50"
              title="Refresh backend and database status"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-emerald-600' : ''}`} />
              <span className="hidden sm:inline">Health</span>
            </button>

            {/* Auth Action Buttons in Header */}
            {isAuthenticated ? (
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => onNavigate('profile')}
                  className="hidden sm:inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                >
                  <UserIcon className="w-3.5 h-3.5 text-slate-500" />
                  <span>{user?.full_name?.split(' ')[0] || 'Profile'}</span>
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-medium text-rose-600 bg-rose-50 border border-rose-200 rounded-lg hover:bg-rose-100 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Sign Out</span>
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => onNavigate('login')}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
                >
                  <LogIn className="w-3.5 h-3.5 text-slate-500" />
                  <span>Sign In</span>
                </button>
                <button
                  type="button"
                  onClick={() => onNavigate('register')}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-semibold text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 transition-colors shadow-xs"
                >
                  <UserPlus className="w-3.5 h-3.5" />
                  <span>Register</span>
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Unverified Email Warning Banner */}
        {isAuthenticated && user && !user.is_email_verified && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 sm:px-8 py-2.5 text-xs text-amber-900 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span>
                <strong>Action Recommended:</strong> Your email ({user.email}) is unverified.
                Check your inbox for the activation link.
              </span>
            </div>
            <div className="flex items-center space-x-3">
              {resendStatus && <span className="text-[11px] text-amber-800">{resendStatus}</span>}
              <button
                type="button"
                onClick={handleResendVerification}
                disabled={isResending}
                className="font-medium text-amber-800 hover:text-amber-950 underline disabled:opacity-50 text-[11px]"
              >
                {isResending ? 'Sending...' : 'Resend Email'}
              </button>
              <button
                type="button"
                onClick={() => onNavigate('verify-email')}
                className="px-2.5 py-1 bg-amber-200 hover:bg-amber-300 text-amber-900 rounded font-medium text-[11px] transition-colors"
              >
                Enter Token
              </button>
            </div>
          </div>
        )}

        {/* Incomplete Onboarding Banner */}
        {isAuthenticated && user && !user.onboarding_completed && currentView !== 'onboarding' && (
          <div className="bg-emerald-50 border-b border-emerald-200 px-4 sm:px-8 py-2.5 text-xs text-emerald-900 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              <span>Complete your account personalization for an optimized India-first setup.</span>
            </div>
            <button
              type="button"
              onClick={() => onNavigate('onboarding')}
              className="inline-flex items-center space-x-1 font-semibold text-emerald-700 hover:text-emerald-900 text-xs"
            >
              <span>Resume Setup</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Page Content */}
        <main className="flex-1 p-4 sm:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
};
