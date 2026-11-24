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
} from 'lucide-react';
import { config } from '../lib/config';
import { Badge } from '../components/common/Badge';

interface AppShellProps {
  children: React.ReactNode;
  backendReachable: boolean;
  databaseReady: boolean;
  isLoading: boolean;
  onRefresh: () => void;
}

interface NavSection {
  title: string;
  items: {
    name: string;
    icon: React.ElementType;
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
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navigationSections: NavSection[] = [
    {
      title: 'Current Foundation',
      items: [
        { name: 'System Foundation', icon: ShieldCheck, active: true },
      ],
    },
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
        { name: 'Settings', icon: Settings, futurePhase: 'Phase 1' },
      ],
    },
  ];

  const sidebarContent = (
    <div className="flex flex-col h-full bg-slate-900 text-slate-300">
      {/* Brand Header */}
      <div className="px-6 py-5 border-b border-slate-800 flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold text-lg">
              ₹
            </div>
            <div>
              <span className="font-semibold text-white tracking-tight text-sm">
                {config.appTitle}
              </span>
              <div className="text-[10px] text-slate-400 font-mono tracking-wider">
                INDIA SAAS • v0.1.0
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6 scrollbar-thin">
        {navigationSections.map((section) => (
          <div key={section.title}>
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-3 mb-2">
              {section.title}
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                if (item.active) {
                  return (
                    <div
                      key={item.name}
                      className="flex items-center justify-between px-3 py-2 rounded-lg bg-emerald-950/60 text-emerald-300 border border-emerald-500/30 text-xs font-medium cursor-default"
                    >
                      <div className="flex items-center space-x-2.5">
                        <Icon className="w-4 h-4 text-emerald-400" />
                        <span>{item.name}</span>
                      </div>
                      <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    </div>
                  );
                }

                return (
                  <div
                    key={item.name}
                    className="flex items-center justify-between px-3 py-1.5 rounded-lg text-slate-400 hover:text-slate-300 text-xs select-none group"
                    title={`This module is scheduled for ${item.futurePhase}`}
                  >
                    <div className="flex items-center space-x-2.5">
                      <Icon className="w-4 h-4 text-slate-500 group-hover:text-slate-400" />
                      <span>{item.name}</span>
                    </div>
                    {item.futurePhase && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono border border-slate-700/60">
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
        <div className="flex items-center justify-between mb-2">
          <span className="text-slate-400">Environment</span>
          <span className="text-slate-300 font-mono text-[11px] bg-slate-800 px-2 py-0.5 rounded">
            Development
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Phase</span>
          <span className="text-emerald-400 font-medium text-[11px]">Phase 0</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block w-72 flex-shrink-0 border-r border-slate-800">
        <div className="fixed top-0 bottom-0 w-72">
          {sidebarContent}
        </div>
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
                <Badge variant="info">Phase 0 Foundation</Badge>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                Multi-User SaaS Architecture • India Locale (INR, FY Apr–Mar)
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

            {/* Manual Refresh Button */}
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-xs disabled:opacity-50"
              title="Refresh backend and database status"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-emerald-600' : ''}`} />
              <span className="hidden sm:inline">Check Health</span>
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-4 sm:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
