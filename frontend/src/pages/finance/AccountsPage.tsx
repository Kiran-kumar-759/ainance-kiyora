import React, { useState, useEffect } from 'react';
import {
  Wallet,
  CreditCard,
  Plus,
  Archive,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Landmark,
  Edit2,
  RotateCcw,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import { FinancialAccount, AccountType } from '../../types/finance';
import { formatINR } from '../../lib/formatters';

interface AccountsPageProps {
  onNavigate: (view: string) => void;
}

export const AccountsPage: React.FC<AccountsPageProps> = ({ onNavigate }) => {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<'active' | 'archived' | 'all'>('active');

  // Modals state
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [editingAccount, setEditingAccount] = useState<FinancialAccount | null>(null);
  const [correctingAccount, setCorrectingAccount] = useState<FinancialAccount | null>(null);

  // Form states
  const [formData, setFormData] = useState({
    name: '',
    account_type: 'savings' as AccountType,
    institution_name: '',
    account_identifier: '',
    opening_balance: '0.00',
    currency: 'INR',
  });
  const [correctedBalance, setCorrectedBalance] = useState<string>('');
  const [formSubmitting, setFormSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchAccounts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await financeApi.listAccounts(true);
      setAccounts(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch financial accounts.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handleOpenAdd = () => {
    setFormData({
      name: '',
      account_type: 'savings',
      institution_name: '',
      account_identifier: '',
      opening_balance: '0.00',
      currency: 'INR',
    });
    setFormError(null);
    setIsAddModalOpen(true);
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formSubmitting) return;
    if (!formData.name.trim()) {
      setFormError('Account name is required.');
      return;
    }
    const obStr = formData.opening_balance.trim();
    const ob = Number(obStr);
    if (obStr === '' || isNaN(ob) || ob < 0) {
      setFormError('Opening balance must be a valid non-negative number.');
      return;
    }
    if (!/^\d+(\.\d{1,2})?$/.test(obStr)) {
      setFormError('Opening balance supports at most 2 decimal places.');
      return;
    }

    setFormSubmitting(true);
    setFormError(null);
    setSuccessMessage(null);
    try {
      const created = await financeApi.createAccount({
        name: formData.name.trim(),
        account_type: formData.account_type,
        institution_name: formData.institution_name.trim() || null,
        account_identifier: formData.account_identifier.trim() || null,
        opening_balance: obStr,
        currency: 'INR',
      });
      setIsAddModalOpen(false);
      await fetchAccounts();
      setSuccessMessage(
        `Account "${created.name}" created with balance ${formatINR(created.current_balance)}.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create financial account.';
      setFormError(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleUpdateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAccount || formSubmitting) return;
    if (!editingAccount.name.trim()) {
      setFormError('Account name is required.');
      return;
    }

    setFormSubmitting(true);
    setFormError(null);
    setSuccessMessage(null);
    try {
      const updated = await financeApi.updateAccount(editingAccount.id, {
        name: editingAccount.name.trim(),
        account_type: editingAccount.account_type,
        institution_name: editingAccount.institution_name?.trim() || null,
        account_identifier: editingAccount.account_identifier?.trim() || null,
      });
      setEditingAccount(null);
      await fetchAccounts();
      setSuccessMessage(`Account "${updated.name}" updated.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update account.';
      setFormError(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleCorrectOpeningBalance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!correctingAccount || formSubmitting) return;
    const obStr = correctedBalance.trim();
    const ob = Number(obStr);
    if (obStr === '' || isNaN(ob) || ob < 0) {
      setFormError('Corrected balance must be a valid non-negative number.');
      return;
    }

    setFormSubmitting(true);
    setFormError(null);
    setSuccessMessage(null);
    try {
      const updated = await financeApi.updateOpeningBalance(correctingAccount.id, obStr);
      setCorrectingAccount(null);
      await fetchAccounts();
      setSuccessMessage(
        `Opening balance recalculated for "${updated.name}" (${formatINR(updated.current_balance)}).`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to correct opening balance.';
      setFormError(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleToggleArchive = async (acc: FinancialAccount) => {
    setError(null);
    setSuccessMessage(null);
    try {
      if (acc.status === 'active') {
        if (confirm(`Archive account "${acc.name}"? Transactions will be preserved.`)) {
          await financeApi.archiveAccount(acc.id);
          await fetchAccounts();
          setSuccessMessage(`Account "${acc.name}" archived. Historical ledger records remain intact.`);
        }
      } else {
        await financeApi.restoreAccount(acc.id);
        await fetchAccounts();
        setSuccessMessage(`Account "${acc.name}" restored to active status.`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Action failed.';
      setError(msg);
    }
  };

  const filteredAccounts = accounts.filter((a) => {
    if (filter === 'active') return a.status === 'active';
    if (filter === 'archived') return a.status === 'archived';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Financial Accounts</h1>
          <p className="text-sm text-gray-600 mt-1">
            Manage your bank accounts, credit cards, digital wallets, and cash reserves.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => onNavigate('banking')}
            className="inline-flex items-center space-x-1.5 px-3 py-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg text-sm font-medium transition-colors border border-indigo-200"
          >
            <Landmark className="w-4 h-4" />
            <span>Connect Demo Bank</span>
          </button>

          <button
            onClick={handleOpenAdd}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Add Account</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs & Refresh */}
      <div className="flex items-center justify-between border-b border-gray-200 pb-3">
        <div className="flex space-x-2">
          {(['active', 'archived', 'all'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg capitalize transition-colors ${
                filter === tab
                  ? 'bg-gray-900 text-white shadow-sm'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {tab} ({accounts.filter((a) => (tab === 'all' ? true : a.status === tab)).length})
            </button>
          ))}
        </div>

        <button
          onClick={fetchAccounts}
          disabled={isLoading}
          className="text-gray-500 hover:text-gray-700 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          title="Refresh Accounts"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Success state */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 flex items-center space-x-3 text-sm">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-600" />
          <div className="flex-1">{successMessage}</div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-700 hover:text-emerald-900"
            aria-label="Dismiss success message"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center space-x-3 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" />
          <div className="flex-1">{error}</div>
          <button onClick={fetchAccounts} className="underline text-red-800 font-medium">
            Retry
          </button>
        </div>
      )}

      {/* Accounts Cards Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="h-44 rounded-xl bg-gray-100 animate-pulse border border-gray-200"
            />
          ))}
        </div>
      ) : filteredAccounts.length === 0 ? (
        <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center">
          <Wallet className="w-12 h-12 mx-auto text-gray-400 mb-3" />
          <h3 className="text-base font-semibold text-gray-900">No accounts found</h3>
          <p className="text-sm text-gray-500 mt-1 max-w-sm mx-auto">
            {filter === 'archived'
              ? 'You do not have any archived accounts.'
              : 'Add your first bank account, credit card, or wallet to begin tracking your finances.'}
          </p>
          <div className="mt-5 flex justify-center space-x-3">
            <button
              onClick={handleOpenAdd}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm"
            >
              + Add Account Manually
            </button>
            <button
              onClick={() => onNavigate('banking')}
              className="px-4 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-sm font-medium rounded-lg"
            >
              Simulate Bank Connection
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredAccounts.map((acc) => {
            const isCC =
              acc.account_type === 'credit_card' || acc.account_type === 'loan_liability';
            return (
              <div
                key={acc.id}
                className={`bg-white rounded-xl border p-5 shadow-sm hover:shadow-md transition-shadow relative flex flex-col justify-between ${
                  acc.status === 'archived'
                    ? 'border-gray-200 opacity-60 bg-gray-50/70'
                    : 'border-gray-200'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div
                        className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                          isCC ? 'bg-rose-50 text-rose-600' : 'bg-blue-50 text-blue-600'
                        }`}
                      >
                        {isCC ? <CreditCard className="w-5 h-5" /> : <Wallet className="w-5 h-5" />}
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900 text-base leading-snug">
                          {acc.name}
                        </h3>
                        <div className="text-xs text-gray-500 mt-0.5">
                          {acc.institution_name || 'Personal Account'}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col items-end space-y-1">
                      {acc.source === 'demo_bank' ? (
                        <span className="px-2 py-0.5 bg-purple-50 text-purple-700 text-[10px] font-bold rounded-full border border-purple-200 uppercase tracking-wide">
                          Demo Bank
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-[10px] font-medium rounded-full">
                          Manual
                        </span>
                      )}
                      {acc.status === 'archived' && (
                        <span className="px-2 py-0.5 bg-amber-50 text-amber-700 text-[10px] font-bold rounded-full border border-amber-200">
                          Archived
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="mt-5">
                    <div className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {isCC ? 'Outstanding Liability' : 'Current Balance'}
                    </div>
                    <div
                      className={`text-2xl font-bold mt-1 ${
                        isCC ? 'text-rose-600' : 'text-gray-900'
                      }`}
                    >
                      {formatINR(acc.current_balance)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1 flex items-center justify-between">
                      <span>Type: {acc.account_type.replace('_', ' ').toUpperCase()}</span>
                      {acc.account_identifier && <span>Ref: {acc.account_identifier}</span>}
                    </div>
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => {
                        setEditingAccount({ ...acc });
                        setFormError(null);
                      }}
                      className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                      title="Edit Account"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        setCorrectingAccount(acc);
                        setCorrectedBalance(String(acc.opening_balance));
                        setFormError(null);
                      }}
                      className="p-1.5 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                      title="Correct Opening Balance"
                    >
                      <SlidersHorizontal className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <button
                    onClick={() => handleToggleArchive(acc)}
                    className={`inline-flex items-center space-x-1 font-medium transition-colors ${
                      acc.status === 'active'
                        ? 'text-gray-500 hover:text-amber-700'
                        : 'text-emerald-600 hover:text-emerald-800'
                    }`}
                  >
                    {acc.status === 'active' ? (
                      <>
                        <Archive className="w-3.5 h-3.5" />
                        <span>Archive</span>
                      </>
                    ) : (
                      <>
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Restore</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Account Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <button
              onClick={() => setIsAddModalOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-gray-900">Create Financial Account</h3>
            <p className="text-xs text-gray-500 mt-1">
              Add a new account to your personal finance ledger.
            </p>

            {formError && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateAccount} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Account Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. HDFC Salary, ICICI Savings, Cash Wallet"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Account Type *
                  </label>
                  <select
                    value={formData.account_type}
                    onChange={(e) =>
                      setFormData({ ...formData, account_type: e.target.value as AccountType })
                    }
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="savings">Savings Account</option>
                    <option value="current">Current Account</option>
                    <option value="cash">Cash in Hand</option>
                    <option value="credit_card">Credit Card (Liability)</option>
                    <option value="digital_wallet">Digital Wallet / UPI</option>
                    <option value="other">Other Financial Account</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Currency</label>
                  <input
                    type="text"
                    disabled
                    value="INR (₹)"
                    className="w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-lg text-gray-600 font-medium"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Bank / Institution
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. HDFC Bank, SBI"
                    value={formData.institution_name}
                    onChange={(e) =>
                      setFormData({ ...formData, institution_name: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Identifier / Mask
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. ••4821"
                    value={formData.account_identifier}
                    onChange={(e) =>
                      setFormData({ ...formData, account_identifier: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Opening Balance (₹) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={formData.opening_balance}
                  onChange={(e) => setFormData({ ...formData, opening_balance: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono"
                />
                <p className="text-[11px] text-gray-500 mt-1">
                  Starting balance will be recorded as an opening position in the financial ledger.
                </p>
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors flex items-center space-x-1.5"
                >
                  {formSubmitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Save Account</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Account Modal */}
      {editingAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <button
              onClick={() => setEditingAccount(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-gray-900">Edit Financial Account</h3>
            <p className="text-xs text-gray-500 mt-1">Update display details for this account.</p>

            {formError && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {formError}
              </div>
            )}

            <form onSubmit={handleUpdateAccount} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Account Name *
                </label>
                <input
                  type="text"
                  required
                  value={editingAccount.name}
                  onChange={(e) => setEditingAccount({ ...editingAccount, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Account Type
                </label>
                <select
                  value={editingAccount.account_type}
                  onChange={(e) =>
                    setEditingAccount({
                      ...editingAccount,
                      account_type: e.target.value as AccountType,
                    })
                  }
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                >
                  <option value="savings">Savings Account</option>
                  <option value="current">Current Account</option>
                  <option value="cash">Cash in Hand</option>
                  <option value="credit_card">Credit Card (Liability)</option>
                  <option value="digital_wallet">Digital Wallet / UPI</option>
                  <option value="other">Other Financial Account</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Institution
                  </label>
                  <input
                    type="text"
                    value={editingAccount.institution_name || ''}
                    onChange={(e) =>
                      setEditingAccount({ ...editingAccount, institution_name: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Identifier Mask
                  </label>
                  <input
                    type="text"
                    value={editingAccount.account_identifier || ''}
                    onChange={(e) =>
                      setEditingAccount({ ...editingAccount, account_identifier: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  />
                </div>
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setEditingAccount(null)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Correct Opening Balance Modal */}
      {correctingAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <button
              onClick={() => setCorrectingAccount(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-gray-900">Correct Opening Balance</h3>
            <p className="text-xs text-gray-500 mt-1">
              Adjust starting position for &ldquo;{correctingAccount.name}&rdquo;. The financial
              ledger will reverse previous opening entries and recalculate all affected balances.
            </p>

            {formError && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {formError}
              </div>
            )}

            <form onSubmit={handleCorrectOpeningBalance} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Correct Opening Balance (₹) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={correctedBalance}
                  onChange={(e) => setCorrectedBalance(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg font-mono focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setCorrectingAccount(null)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm"
                >
                  Recalculate Ledger
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
