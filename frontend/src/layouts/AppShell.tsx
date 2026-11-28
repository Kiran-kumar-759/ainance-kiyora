import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  BarChart3,
  Wallet,
  Receipt,
  FileSpreadsheet,
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
  ChevronLeft,
  LogIn,
  UserPlus,
  ArrowRightLeft,
  Landmark,
  Bell,
  BellRing,
  CheckCheck,
  Home,
} from 'lucide-react';
import { Badge } from '../components/common/Badge';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../services/authApi';
import { billsApi } from '../services/billsApi';
import { getPathForView } from '../lib/routes';
import { AppNotification } from '../types/bills';

interface AppShellProps {
  children: React.ReactNode;
  backendReachable: boolean;
  databaseReady: boolean;
  isLoading: boolean;
  onRefresh: () => void;
  currentView: string;
  onNavigate: (view: string) => void;
}

interface NavItem {
  name: string;
  icon: React.ElementType;
  view: string;
  active?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const VIEW_TITLES: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: 'Financial Overview', subtitle: 'Balances, cashflow, upcoming commitments & AI highlights' },
  analytics: { title: 'Spending Analytics', subtitle: 'Cashflow trends, category deep-dives & period comparisons' },
  reports: { title: 'Financial Reports', subtitle: 'Statements, monthly summaries & CSV exports' },
  accounts: { title: 'Accounts & Cards', subtitle: 'Bank balances, credit limits, wallets & investments' },
  transactions: { title: 'Transactions Ledger', subtitle: 'Filterable income, expense & recurring ledger' },
  transfers: { title: 'Internal Transfers', subtitle: 'Zero-sum fund movements across your accounts' },
  imports: { title: 'Bank Statement Imports', subtitle: 'CSV & XLSX column mapping, deduplication & commit' },
  banking: { title: 'Bank Connections', subtitle: 'Connected bank feeds & sync audit history' },
  bills: { title: 'Bills & Utilities', subtitle: 'Scheduled obligations, partial payments & recurring templates' },
  subscriptions: { title: 'OTT & Subscriptions', subtitle: 'Recurring plans, paid months tracker & renewal hygiene' },
  loans: { title: 'Loans & EMIs', subtitle: 'Amortization schedules, rate revisions & prepayments' },
  reminders: { title: 'Reminders & Notifications', subtitle: 'Commitment alerts, dispatch logs & SMTP email status' },
  intelligence: { title: 'AI Expense Intelligence', subtitle: 'Anomaly detection, recurring discovery & ML rules' },
  forecasting: { title: 'Cashflow Forecasting', subtitle: 'Multi-horizon projections, stress scenarios & backtests' },
  assistant: { title: 'AI Finance Assistant', subtitle: 'Grounded ledger RAG, web research & voice actions' },
  documents: { title: 'Documents & Email Imports', subtitle: 'OCR receipt review, vault & Gmail bill ingestion' },
  integrations: { title: 'Integrations Center', subtitle: 'Gmail, SMTP delivery, Groq AI, web search & OCR status' },
  settings: { title: 'Workspace Settings', subtitle: 'Profile, security, regional preferences & AI controls' },
  profile: { title: 'My Profile', subtitle: 'Identity & account details' },
  preferences: { title: 'Regional Preferences', subtitle: 'Currency (INR), timezone & notification channels' },
  sessions: { title: 'Active Sessions', subtitle: 'Device sessions & security controls' },
  onboarding: { title: 'Setup & Onboarding', subtitle: 'Configure your personal finance workspace' },
  foundation: { title: 'Platform Overview & Status', subtitle: 'Live backend readiness & product architecture' },
};

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const { user, preferences, isAuthenticated, logout } = useAuth();
  const compactSidebar = Boolean(preferences?.notification_preferences?.compact_sidebar);
  const onboardingLocked = Boolean(isAuthenticated && user && user.onboarding_completed === false);
  const [resendStatus, setResendStatus] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);

  const loadNotifications = async () => {
    if (!isAuthenticated) {
      setNotifications([]);
      setUnreadCount(0);
      return;
    }
    try {
      const res = await billsApi.listNotifications(false);
      setNotifications(Array.isArray(res?.items) ? res.items.slice(0, 8) : []);
      setUnreadCount(typeof res?.unread_count === 'number' ? res.unread_count : 0);
    } catch {
      // Non-fatal in shell header when offline or during partial renders
    }
  };

  useEffect(() => {
    void loadNotifications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, currentView]);

  const handleMarkNotificationRead = async (notificationId: string) => {
    try {
      await billsApi.markNotificationRead(notificationId);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // ignore
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await billsApi.markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  };

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
    setUserMenuOpen(false);
    await logout();
    onNavigate('login');
  };

  const navigationSections: NavSection[] = [
    {
      title: 'Overview',
      items: [
        { name: 'Dashboard', icon: LayoutDashboard, view: 'dashboard', active: currentView === 'dashboard' },
        { name: 'Analytics', icon: BarChart3, view: 'analytics', active: currentView === 'analytics' },
        { name: 'Reports', icon: FileText, view: 'reports', active: currentView === 'reports' },
      ],
    },
    {
      title: 'Money Management',
      items: [
        { name: 'Accounts', icon: Wallet, view: 'accounts', active: currentView === 'accounts' },
        { name: 'Transactions', icon: Receipt, view: 'transactions', active: currentView === 'transactions' },
        { name: 'Transfers', icon: ArrowRightLeft, view: 'transfers', active: currentView === 'transfers' },
        { name: 'Imports', icon: FileSpreadsheet, view: 'imports', active: currentView === 'imports' },
        { name: 'Bank Connections', icon: Landmark, view: 'banking', active: currentView === 'banking' },
      ],
    },
    {
      title: 'Payments & Commitments',
      items: [
        { name: 'Bills', icon: CalendarDays, view: 'bills', active: currentView === 'bills' },
        { name: 'Subscriptions', icon: CreditCard, view: 'subscriptions', active: currentView === 'subscriptions' },
        { name: 'Loans & EMIs', icon: Landmark, view: 'loans', active: currentView === 'loans' },
        {
          name: 'Reminders & Notifications',
          icon: BellRing,
          view: 'reminders',
          active: currentView === 'reminders',
        },
      ],
    },
    {
      title: 'Intelligence',
      items: [
        { name: 'AI Insights', icon: Sparkles, view: 'intelligence', active: currentView === 'intelligence' },
        { name: 'Forecasting', icon: TrendingUp, view: 'forecasting', active: currentView === 'forecasting' },
        { name: 'AI Assistant', icon: Bot, view: 'assistant', active: currentView === 'assistant' },
      ],
    },
    {
      title: 'Documents & Settings',
      items: [
        { name: 'Documents', icon: FolderOpen, view: 'documents', active: currentView === 'documents' },
        { name: 'Integrations', icon: Plug, view: 'integrations', active: currentView === 'integrations' },
        { name: 'Settings', icon: Settings, view: 'settings', active: currentView === 'settings' },
        ...(isAuthenticated
          ? [
              {
                name: 'Onboarding Wizard',
                icon: Sparkles,
                view: 'onboarding',
                active: currentView === 'onboarding',
              },
            ]
          : []),
      ],
    },
  ];

  const handleNavClick = (view: string) => {
    onNavigate(view);
    setMobileMenuOpen(false);
    setUserMenuOpen(false);
  };

  const viewMeta = VIEW_TITLES[currentView] || {
    title: 'FinSight AI Workspace',
    subtitle: 'Personal Finance Manager — India',
  };

  const renderSidebarContent = (collapsed: boolean) => (
    <div className="flex flex-col h-full bg-navy-900 text-slate-300 border-r border-slate-800/80">
      {/* Brand Header */}
      <div className="h-16 px-4 flex items-center justify-between border-b border-slate-800/80 shrink-0">
        <button
          type="button"
          onClick={() => handleNavClick(isAuthenticated ? 'dashboard' : 'foundation')}
          className="flex items-center gap-2.5 text-left group focus:outline-none"
          title="FinSight AI Home"
        >
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm shadow-md shadow-indigo-950/50 shrink-0 group-hover:scale-105 transition-transform">
            ₹
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <h1 className="text-sm font-bold text-white leading-tight truncate">FinSight AI</h1>
              <p className="text-[10px] text-indigo-300 font-medium tracking-wider uppercase">
                India Finance
              </p>
            </div>
          )}
        </button>

        <button
          type="button"
          onClick={() => setSidebarCollapsed((c) => !c)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="hidden lg:flex p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>

        <button
          type="button"
          className="lg:hidden p-1.5 text-slate-400 hover:text-white"
          onClick={() => setMobileMenuOpen(false)}
          aria-label="Close navigation menu"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {navigationSections.map((section) => (
          <div key={section.title}>
            {!collapsed && (
              <p className="px-2.5 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {section.title}
              </p>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.view}>
                    <button
                      type="button"
                      onClick={() => handleNavClick(item.view)}
                      aria-label={item.name}
                      title={collapsed ? item.name : undefined}
                      className={`w-full flex items-center ${
                        collapsed ? 'justify-center px-2' : 'justify-between px-2.5'
                      } ${compactSidebar ? 'py-1.5' : 'py-2'} rounded-xl text-xs font-medium transition-all duration-150 ${
                        item.active
                          ? 'bg-gradient-to-r from-indigo-600/25 to-violet-600/15 text-white border border-indigo-500/35 shadow-sm'
                          : 'text-slate-400 hover:bg-slate-800/80 hover:text-slate-100 border border-transparent'
                      }`}
                    >
                      <span className="flex items-center gap-2.5 min-w-0">
                        <Icon
                          className={`w-4 h-4 shrink-0 ${
                            item.active ? 'text-indigo-400' : 'text-slate-400'
                          }`}
                        />
                        {!collapsed && <span className="truncate">{item.name}</span>}
                      </span>
                      {!collapsed && item.active && (
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      {/* Bottom Health & Foundation Link */}
      <div className="p-3 border-t border-slate-800/80 space-y-2 shrink-0 bg-navy-950/60">
        {!collapsed ? (
          <>
            <button
              type="button"
              onClick={() => handleNavClick('foundation')}
              className="w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-[11px] font-medium text-slate-400 hover:bg-slate-800/80 hover:text-slate-100 transition-colors"
            >
              <span className="flex items-center gap-2">
                <Home className="w-3.5 h-3.5 text-indigo-400" />
                <span>Public Overview & Status</span>
              </span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-[11px]">
              <span className="flex items-center gap-1.5 text-slate-400">
                <span
                  className={`w-2 h-2 rounded-full ${
                    backendReachable && databaseReady
                      ? 'bg-emerald-400'
                      : backendReachable
                      ? 'bg-amber-400'
                      : 'bg-rose-500'
                  }`}
                />
                <span>API & PostgreSQL</span>
              </span>
              <span className="font-semibold text-slate-200">
                {backendReachable && databaseReady
                  ? 'Healthy'
                  : backendReachable
                  ? 'Degraded'
                  : 'Offline'}
              </span>
            </div>
          </>
        ) : (
          <button
            type="button"
            onClick={() => handleNavClick('foundation')}
            aria-label="Public Overview & Status"
            title="Public Overview & Status"
            className="w-full flex justify-center py-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
          </button>
        )}

        {!isAuthenticated && !collapsed && (
          <div className="grid grid-cols-2 gap-1.5 pt-1">
            <button
              type="button"
              onClick={() => handleNavClick('login')}
              className="flex items-center justify-center gap-1 py-1.5 text-xs font-medium rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700"
            >
              <LogIn className="w-3 h-3" />
              <span>Login</span>
            </button>
            <button
              type="button"
              onClick={() => handleNavClick('register')}
              className="flex items-center justify-center gap-1 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-500"
            >
              <UserPlus className="w-3 h-3" />
              <span>Register</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900">
      {/* Desktop Sidebar (hidden during mandatory first-time onboarding) */}
      {!onboardingLocked && (
        <aside
          className={`hidden lg:block shrink-0 transition-all duration-200 ${
            sidebarCollapsed ? 'w-[72px]' : 'w-64'
          }`}
        >
          <div className="sticky top-0 h-screen">{renderSidebarContent(sidebarCollapsed)}</div>
        </aside>
      )}

      {/* Mobile Drawer */}
      {!onboardingLocked && mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="relative z-10 w-72 max-w-[85vw] h-full shadow-2xl">
            {renderSidebarContent(false)}
          </aside>
        </div>
      )}

      {/* Main Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Sticky Glass Topbar */}
        <header className="sticky top-0 z-30 h-16 px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-3 bg-white/85 backdrop-blur-md border-b border-slate-200/80">
          <div className="flex items-center gap-3 min-w-0">
            {!onboardingLocked && (
              <button
                type="button"
                className="lg:hidden p-2 -ml-1.5 rounded-lg text-slate-600 hover:bg-slate-100"
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Open navigation menu"
              >
                <Menu className="w-5 h-5" />
              </button>
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-sm sm:text-base font-bold text-slate-900 truncate">
                  {viewMeta.title}
                </h1>
                <a
                  href={getPathForView(currentView)}
                  onClick={(e) => {
                    e.preventDefault();
                    onNavigate(currentView);
                  }}
                  title={`Direct page link: ${getPathForView(currentView)}`}
                  className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-md bg-slate-100 hover:bg-indigo-50 text-slate-500 hover:text-indigo-700 font-mono text-[10px] border border-slate-200/80 transition-colors"
                >
                  {getPathForView(currentView)}
                </a>
                <Badge variant="info" className="hidden md:inline-flex">
                  {preferences?.preferred_currency || 'INR'} • {preferences?.locale || 'en-IN'}
                </Badge>
              </div>
              <p className="text-[11px] text-slate-500 truncate hidden sm:block">
                {viewMeta.subtitle}
              </p>
            </div>
          </div>

          {/* Right Controls */}
          <div className="flex items-center gap-2 shrink-0">
            {!onboardingLocked && (
              <button
                type="button"
                onClick={() => onNavigate('assistant')}
                className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-indigo-50 to-violet-50 hover:from-indigo-100 hover:to-violet-100 border border-indigo-200/80 text-indigo-700 text-xs font-semibold transition-colors"
              >
                <Bot className="w-3.5 h-3.5 text-indigo-600" />
                <span>Ask AI</span>
              </button>
            )}

            <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 bg-slate-50/90 text-[11px]">
              <Server
                className={`w-3.5 h-3.5 ${backendReachable ? 'text-emerald-600' : 'text-rose-500'}`}
              />
              <span className="font-medium text-slate-600">API</span>
              <span className="text-slate-300">|</span>
              <Database
                className={`w-3.5 h-3.5 ${databaseReady ? 'text-emerald-600' : 'text-amber-500'}`}
              />
              <span className="font-medium text-slate-600">PG</span>
            </div>

            <button
              type="button"
              onClick={onRefresh}
              disabled={isLoading}
              aria-label="Refresh system status"
              title="Refresh system status"
              className="p-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>

            {isAuthenticated && !onboardingLocked && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setNotificationsOpen((prev) => !prev)}
                  aria-label="Notifications"
                  className="relative p-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors"
                >
                  <Bell className="w-4 h-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 px-1.5 min-w-[16px] h-4 rounded-full bg-indigo-600 text-white text-[10px] font-bold flex items-center justify-center shadow-xs">
                      {unreadCount}
                    </span>
                  )}
                </button>

                {notificationsOpen && (
                  <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white border border-slate-200 shadow-glass z-50 overflow-hidden animate-slideUp">
                    <div className="px-4 py-3 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-800">
                        Notifications ({unreadCount} unread)
                      </span>
                      <div className="flex items-center gap-2.5">
                        {unreadCount > 0 && (
                          <button
                            type="button"
                            onClick={handleMarkAllRead}
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-800"
                          >
                            <CheckCheck className="w-3.5 h-3.5" />
                            <span>Mark all read</span>
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="max-h-72 overflow-y-auto divide-y divide-slate-100">
                      {notifications.length === 0 ? (
                        <div className="p-6 text-center text-xs text-slate-500">
                          No notifications yet. Upcoming bill, subscription, and EMI reminders will appear here.
                        </div>
                      ) : (
                        notifications.map((n) => (
                          <div
                            key={n.id}
                            className={`px-4 py-3 text-xs transition-colors ${
                              n.is_read ? 'bg-white' : 'bg-indigo-50/45'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="font-semibold text-slate-900">{n.title}</p>
                              {!n.is_read && (
                                <button
                                  type="button"
                                  onClick={() => handleMarkNotificationRead(n.id)}
                                  className="text-[10px] text-indigo-600 hover:underline shrink-0"
                                >
                                  Read
                                </button>
                              )}
                            </div>
                            <p className="text-slate-600 mt-0.5 leading-snug">{n.message}</p>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
                      <button
                        type="button"
                        onClick={() => {
                          setNotificationsOpen(false);
                          onNavigate('reminders');
                        }}
                        className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                      >
                        Open Reminders & Notifications →
                      </button>
                      <button
                        type="button"
                        onClick={() => setNotificationsOpen(false)}
                        className="text-xs text-slate-500 hover:text-slate-700"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {isAuthenticated && user ? (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setUserMenuOpen((prev) => !prev)}
                  className="flex items-center gap-2 pl-2 pr-2.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors"
                >
                  <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white text-xs font-bold flex items-center justify-center">
                    {(user.full_name || user.email || 'U').charAt(0).toUpperCase()}
                  </div>
                  <span className="hidden md:inline text-xs font-semibold text-slate-800 max-w-[110px] truncate">
                    {user.full_name?.split(' ')[0] || 'Account'}
                  </span>
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-white border border-slate-200 shadow-glass py-1.5 z-50 animate-slideUp">
                    <div className="px-3.5 py-2 border-b border-slate-100">
                      <p className="text-xs font-semibold text-slate-900 truncate">{user.full_name}</p>
                      <p className="text-[11px] text-slate-500 truncate">{user.email}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleNavClick('profile')}
                      className="w-full px-3.5 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                    >
                      <UserIcon className="w-3.5 h-3.5 text-slate-400" />
                      <span>My Profile</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleNavClick('preferences')}
                      className="w-full px-3.5 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                    >
                      <Sliders className="w-3.5 h-3.5 text-slate-400" />
                      <span>Regional Preferences</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleNavClick('sessions')}
                      className="w-full px-3.5 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                    >
                      <Smartphone className="w-3.5 h-3.5 text-slate-400" />
                      <span>Active Sessions</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleNavClick('settings')}
                      className="w-full px-3.5 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                    >
                      <Settings className="w-3.5 h-3.5 text-slate-400" />
                      <span>Workspace Settings</span>
                    </button>
                    <div className="my-1 border-t border-slate-100" />
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="w-full px-3.5 py-2 text-left text-xs font-semibold text-rose-600 hover:bg-rose-50 flex items-center gap-2"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => onNavigate('login')}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Login
                </button>
                <button
                  type="button"
                  onClick={() => onNavigate('register')}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs"
                >
                  Get Started
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Contextual Verification & Onboarding Banners */}
        {isAuthenticated && user && (!user.is_email_verified || !user.onboarding_completed) && (
          <div className="px-4 sm:px-6 lg:px-8 pt-4 space-y-2 max-w-[1440px] w-full mx-auto">
            {!user.is_email_verified && (
              <div className="bg-amber-50/95 border border-amber-200/90 rounded-xl px-4 py-2.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs">
                <div className="flex items-center gap-2 text-amber-900">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    Email address <strong>{user.email}</strong> is unverified.{' '}
                    {resendStatus && <strong className="ml-1 underline">{resendStatus}</strong>}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={handleResendVerification}
                    disabled={isResending}
                    className="px-2.5 py-1 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-900 font-semibold transition-colors"
                  >
                    {isResending ? 'Sending...' : 'Resend Link'}
                  </button>
                  <button
                    type="button"
                    onClick={() => onNavigate('verify-email')}
                    className="px-2.5 py-1 rounded-lg bg-white border border-amber-300 text-amber-900 font-semibold hover:bg-amber-50"
                  >
                    Verify Email
                  </button>
                </div>
              </div>
            )}

            {!user.onboarding_completed && currentView !== 'onboarding' && (
              <div className="bg-indigo-50/90 border border-indigo-200 rounded-xl px-4 py-2.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs">
                <div className="flex items-center gap-2 text-indigo-900">
                  <Sparkles className="w-4 h-4 text-indigo-600 shrink-0" />
                  <span>
                    Complete your onboarding setup (INR, timezone, and optional account import) to personalize your workspace.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => onNavigate('onboarding')}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 shrink-0"
                >
                  <span>Resume Onboarding</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Main Content Viewport */}
        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6">
          <div className="max-w-[1440px] mx-auto animate-fadeIn">{children}</div>
        </main>
      </div>
    </div>
  );
};
