import { TransactionNavigationFilters } from '../types/analytics';

export const VIEW_PATHS: Record<string, string> = {
  foundation: '/',
  login: '/login',
  register: '/register',
  'forgot-password': '/forgot-password',
  'reset-password': '/reset-password',
  'verify-email': '/verify-email',
  onboarding: '/onboarding',
  dashboard: '/dashboard',
  accounts: '/accounts',
  transactions: '/transactions',
  transfers: '/transfers',
  banking: '/banking',
  imports: '/imports',
  analytics: '/analytics',
  reports: '/reports',
  bills: '/bills',
  subscriptions: '/subscriptions',
  loans: '/loans',
  reminders: '/reminders',
  documents: '/documents',
  integrations: '/integrations',
  intelligence: '/intelligence',
  forecasting: '/forecasting',
  assistant: '/assistant',
  profile: '/profile',
  preferences: '/preferences',
  sessions: '/sessions',
  settings: '/settings',
};

const PATH_TO_VIEW: Record<string, string> = Object.entries(VIEW_PATHS).reduce(
  (acc, [view, path]) => {
    acc[path] = view;
    return acc;
  },
  {} as Record<string, string>
);

export const VIEW_DOCUMENT_TITLES: Record<string, string> = {
  foundation: 'FinSight AI — Personal Finance Manager (India)',
  login: 'Sign In — FinSight AI',
  register: 'Create Account — FinSight AI',
  'forgot-password': 'Forgot Password — FinSight AI',
  'reset-password': 'Reset Password — FinSight AI',
  'verify-email': 'Verify Email — FinSight AI',
  onboarding: 'Setup & Onboarding — FinSight AI',
  dashboard: 'Dashboard — FinSight AI',
  accounts: 'Accounts & Cards — FinSight AI',
  transactions: 'Transactions Ledger — FinSight AI',
  transfers: 'Internal Transfers — FinSight AI',
  banking: 'Bank Connections — FinSight AI',
  imports: 'Bank Statement Imports — FinSight AI',
  analytics: 'Spending Analytics — FinSight AI',
  reports: 'Financial Reports — FinSight AI',
  bills: 'Bills & Utilities — FinSight AI',
  subscriptions: 'OTT & Subscriptions — FinSight AI',
  loans: 'Loans & EMIs — FinSight AI',
  reminders: 'Reminders & Notifications — FinSight AI',
  documents: 'Documents & Email Imports — FinSight AI',
  integrations: 'Integrations Center — FinSight AI',
  intelligence: 'AI Expense Intelligence — FinSight AI',
  forecasting: 'Cashflow Forecasting — FinSight AI',
  assistant: 'AI Finance Assistant — FinSight AI',
  profile: 'My Profile — FinSight AI',
  preferences: 'Regional Preferences — FinSight AI',
  sessions: 'Active Sessions — FinSight AI',
  settings: 'Workspace Settings — FinSight AI',
};

export function getPathForView(
  view: string,
  txFilters?: TransactionNavigationFilters | null
): string {
  const basePath = VIEW_PATHS[view] || '/';
  if (view === 'transactions' && txFilters) {
    const qs = new URLSearchParams();
    if (txFilters.accountId) qs.set('accountId', txFilters.accountId);
    if (txFilters.categoryId) qs.set('categoryId', txFilters.categoryId);
    if (txFilters.transactionType) qs.set('type', txFilters.transactionType);
    if (txFilters.startDate) qs.set('startDate', txFilters.startDate);
    if (txFilters.endDate) qs.set('endDate', txFilters.endDate);
    if (txFilters.source) qs.set('source', txFilters.source);
    const s = qs.toString();
    return s ? `${basePath}?${s}` : basePath;
  }
  return basePath;
}

export function getViewFromLocation(
  pathname?: string,
  search?: string
): {
  view: string;
  token: string;
  txFilters: TransactionNavigationFilters | null;
} {
  const rawPath =
    pathname ?? (typeof window !== 'undefined' ? window.location.pathname : '/');
  const rawSearch =
    search ?? (typeof window !== 'undefined' ? window.location.search : '');

  const normalizedPath =
    rawPath.length > 1 ? rawPath.replace(/\/+$/, '').toLowerCase() : '/';
  const params = new URLSearchParams(rawSearch);

  const token = params.get('token') || '';
  const action = params.get('action') || '';
  if (token) {
    const tokenView =
      action === 'reset-password' || normalizedPath.includes('reset-password')
        ? 'reset-password'
        : 'verify-email';
    return { view: tokenView, token, txFilters: null };
  }

  const matchedView = PATH_TO_VIEW[normalizedPath] || 'foundation';
  let txFilters: TransactionNavigationFilters | null = null;

  if (matchedView === 'transactions' && rawSearch) {
    const next: TransactionNavigationFilters = {};
    const accountId = params.get('accountId');
    const categoryId = params.get('categoryId');
    const transactionType = params.get('type');
    const startDate = params.get('startDate');
    const endDate = params.get('endDate');
    const qSource = params.get('source');
    if (accountId) next.accountId = accountId;
    if (categoryId) next.categoryId = categoryId;
    if (
      transactionType === 'income' ||
      transactionType === 'expense' ||
      transactionType === 'transfer'
    ) {
      next.transactionType = transactionType;
    }
    if (startDate) next.startDate = startDate;
    if (endDate) next.endDate = endDate;
    if (qSource) next.source = qSource;
    if (Object.keys(next).length > 0) {
      txFilters = next;
    }
  }

  return { view: matchedView, token, txFilters };
}

export function syncBrowserUrl(
  view: string,
  options: { replace?: boolean; txFilters?: TransactionNavigationFilters | null } = {}
): void {
  if (typeof window === 'undefined' || !window.history) return;
  const targetUrl = getPathForView(view, options.txFilters);
  const currentUrl = `${window.location.pathname}${window.location.search}`;
  if (currentUrl === targetUrl) return;

  try {
    if (options.replace) {
      window.history.replaceState({ view }, '', targetUrl);
    } else {
      window.history.pushState({ view }, '', targetUrl);
    }
  } catch {
    // Ignore history exceptions in restricted sandboxes
  }
}
