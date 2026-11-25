import React, { useState, useEffect } from 'react';
import {
  Plus,
  Search,
  ArrowDownLeft,
  ArrowUpRight,
  ArrowRightLeft,
  RefreshCw,
  Trash2,
  Edit2,
  X,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Receipt,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import {
  FinancialAccount,
  FinancialCategory,
  FinancialTransaction,
} from '../../types/finance';
import { formatINR, formatDate } from '../../lib/formatters';

import { TransactionNavigationFilters } from '../../types/analytics';

interface TransactionsPageProps {
  onNavigate: (view: string) => void;
  initialFilters?: TransactionNavigationFilters | null;
}

export const TransactionsPage: React.FC<TransactionsPageProps> = ({
  onNavigate,
  initialFilters,
}) => {
  const [transactions, setTransactions] = useState<FinancialTransaction[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Reference data
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [categories, setCategories] = useState<FinancialCategory[]>([]);

  // Filters
  const [accountId, setAccountId] = useState<string>(initialFilters?.accountId || '');
  const [txType, setTxType] = useState<string>(initialFilters?.transactionType || '');
  const [categoryId, setCategoryId] = useState<string>(initialFilters?.categoryId || '');
  const [source, setSource] = useState<string>(initialFilters?.source || '');
  const [search, setSearch] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('date_desc');
  const [startDate, setStartDate] = useState<string>(initialFilters?.startDate || '');
  const [endDate, setEndDate] = useState<string>(initialFilters?.endDate || '');

  useEffect(() => {
    if (!initialFilters) return;
    setAccountId(initialFilters.accountId || '');
    setTxType(initialFilters.transactionType || '');
    setCategoryId(initialFilters.categoryId || '');
    setSource(initialFilters.source || '');
    setStartDate(initialFilters.startDate || '');
    setEndDate(initialFilters.endDate || '');
    setPage(1);
  }, [initialFilters]);

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [editingTx, setEditingTx] = useState<FinancialTransaction | null>(null);
  const [deletingTx, setDeletingTx] = useState<FinancialTransaction | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    account_id: '',
    transaction_type: 'expense' as 'income' | 'expense',
    amount: '',
    category_id: '',
    description: '',
    merchant_payee: '',
    transaction_date: new Date().toISOString().split('T')[0],
    notes: '',
  });
  const [formSubmitting, setFormSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Load accounts and categories on mount
  const loadMetadata = async () => {
    try {
      const [accs, cats] = await Promise.all([
        financeApi.listAccounts(false),
        financeApi.listCategories(),
      ]);
      setAccounts(accs);
      setCategories(cats);
      if (accs.length > 0 && !formData.account_id) {
        setFormData((prev) => ({ ...prev, account_id: accs[0].id }));
      }
    } catch {
      // Fallback gracefully
    }
  };

  useEffect(() => {
    loadMetadata();
  }, []);

  const fetchTransactions = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await financeApi.listTransactions({
        account_id: accountId || undefined,
        transaction_type: txType || undefined,
        category_id: categoryId || undefined,
        source: source || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        search: search.trim() || undefined,
        sort_by: sortBy,
        page,
        page_size: 15,
      });
      setTransactions(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch transactions.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [page, accountId, txType, categoryId, source, sortBy, startDate, endDate]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchTransactions();
  };

  const handleOpenAdd = () => {
    setFormData({
      account_id: accounts.length > 0 ? accounts[0].id : '',
      transaction_type: 'expense',
      amount: '',
      category_id: '',
      description: '',
      merchant_payee: '',
      transaction_date: new Date().toISOString().split('T')[0],
      notes: '',
    });
    setFormError(null);
    setIsAddModalOpen(true);
  };

  const handleCreateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formSubmitting) return;
    if (!formData.account_id) {
      setFormError('Please select an account.');
      return;
    }
    const amt = parseFloat(formData.amount);
    if (isNaN(amt) || amt <= 0) {
      setFormError('Amount must be greater than zero.');
      return;
    }
    const selectedAcc = accounts.find((a) => a.id === formData.account_id);
    if (
      selectedAcc &&
      selectedAcc.account_type !== 'credit_card' &&
      formData.transaction_type === 'expense' &&
      amt > Number(selectedAcc.current_balance)
    ) {
      setFormError(
        `Insufficient balance in ${selectedAcc.name}. Available balance is ${formatINR(selectedAcc.current_balance)}.`
      );
      return;
    }
    if (!formData.description.trim()) {
      setFormError('Description is required.');
      return;
    }

    setFormSubmitting(true);
    setFormError(null);
    try {
      await financeApi.createTransaction({
        account_id: formData.account_id,
        transaction_type: formData.transaction_type,
        amount: formData.amount,
        category_id: formData.category_id || null,
        description: formData.description.trim(),
        merchant_payee: formData.merchant_payee.trim() || null,
        transaction_date: formData.transaction_date,
        notes: formData.notes.trim() || null,
      });
      setIsAddModalOpen(false);
      await Promise.all([fetchTransactions(), loadMetadata()]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to record transaction.';
      setFormError(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleUpdateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTx || formSubmitting) return;
    const amt = parseFloat(String(editingTx.amount));
    if (isNaN(amt) || amt <= 0) {
      setFormError('Amount must be greater than zero.');
      return;
    }

    setFormSubmitting(true);
    setFormError(null);
    try {
      await financeApi.updateTransaction(editingTx.id, {
        amount: editingTx.amount,
        category_id: editingTx.category_id || null,
        description: editingTx.description.trim(),
        merchant_payee: editingTx.merchant_payee?.trim() || null,
        transaction_date: editingTx.transaction_date,
        notes: editingTx.notes?.trim() || null,
      });
      setEditingTx(null);
      await Promise.all([fetchTransactions(), loadMetadata()]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update transaction.';
      setFormError(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleDeleteTransaction = async () => {
    if (!deletingTx || formSubmitting) return;
    setFormSubmitting(true);
    setFormError(null);
    try {
      await financeApi.deleteTransaction(deletingTx.id);
      setDeletingTx(null);
      await Promise.all([fetchTransactions(), loadMetadata()]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete transaction.';
      setFormError(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const filteredCategoriesForForm = categories.filter(
    (c) => c.category_type === formData.transaction_type
  );

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Transactions</h1>
          <p className="text-sm text-gray-600 mt-1">
            Browse, filter, and record income and expense entries synchronized with your double-entry ledger.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => onNavigate('transfers')}
            className="inline-flex items-center space-x-1.5 px-3 py-2 bg-white text-gray-700 hover:bg-gray-50 border border-gray-200 rounded-lg text-sm font-medium shadow-sm transition-colors"
          >
            <ArrowRightLeft className="w-4 h-4 text-blue-600" />
            <span>Transfer Money</span>
          </button>

          <button
            onClick={handleOpenAdd}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Record Transaction</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Search descriptions, merchants, or notes..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
          >
            Search
          </button>
          <button
            type="button"
            onClick={() => {
              setSearch('');
              setAccountId('');
              setTxType('');
              setCategoryId('');
              setSource('');
              setStartDate('');
              setEndDate('');
              setSortBy('date_desc');
              setPage(1);
            }}
            className="px-3 py-2 text-gray-500 hover:text-gray-700 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            Reset
          </button>
        </form>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 pt-2 border-t border-gray-100 text-xs">
          {/* Account Filter */}
          <div>
            <label className="block text-gray-500 mb-1 font-medium">Account</label>
            <select
              value={accountId}
              onChange={(e) => {
                setAccountId(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          {/* Type Filter */}
          <div>
            <label className="block text-gray-500 mb-1 font-medium">Type</label>
            <select
              value={txType}
              onChange={(e) => {
                setTxType(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Types</option>
              <option value="income">Income</option>
              <option value="expense">Expense</option>
              <option value="transfer">Transfer</option>
            </select>
          </div>

          {/* Category Filter */}
          <div>
            <label className="block text-gray-500 mb-1 font-medium">Category</label>
            <select
              value={categoryId}
              onChange={(e) => {
                setCategoryId(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Source Filter */}
          <div>
            <label className="block text-gray-500 mb-1 font-medium">Source</label>
            <select
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Sources</option>
              <option value="manual">Manual Entry</option>
              <option value="demo_bank">Demo Bank</option>
              <option value="csv_import">CSV Import</option>
              <option value="xlsx_import">XLSX Import</option>
            </select>
          </div>

          {/* Sort By */}
          <div>
            <label className="block text-gray-500 mb-1 font-medium">Sort Order</label>
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
              className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
            >
              <option value="date_desc">Newest First</option>
              <option value="date_asc">Oldest First</option>
              <option value="amount_desc">Highest Amount</option>
              <option value="amount_asc">Lowest Amount</option>
            </select>
          </div>

          {/* Refresh button */}
          <div className="flex items-end">
            <button
              onClick={fetchTransactions}
              disabled={isLoading}
              className="w-full py-1.5 px-3 bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-200 rounded-lg font-medium flex items-center justify-center space-x-1"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center space-x-3 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" />
          <div className="flex-1">{error}</div>
          <button onClick={fetchTransactions} className="underline text-red-800 font-medium">
            Retry
          </button>
        </div>
      )}

      {/* Transactions List */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500 space-y-3">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-blue-600" />
            <p className="text-sm">Loading transactions...</p>
          </div>
        ) : transactions.length === 0 ? (
          <div className="p-12 text-center text-gray-500">
            <Receipt className="w-12 h-12 mx-auto text-gray-300 mb-3" />
            <h3 className="text-base font-semibold text-gray-900">No transactions found</h3>
            <p className="text-sm text-gray-500 mt-1 max-w-sm mx-auto">
              No transactions match your active filters. Try resetting the filters or record a new transaction.
            </p>
            <button
              onClick={handleOpenAdd}
              className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm"
            >
              + Record Transaction
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50/75 text-xs font-semibold text-gray-500 border-b border-gray-200 uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Description & Payee</th>
                  <th className="py-3 px-4">Account</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Source</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-gray-50/70 transition-colors">
                    <td className="py-3 px-4 text-xs font-medium text-gray-600 whitespace-nowrap">
                      {formatDate(tx.transaction_date)}
                    </td>

                    <td className="py-3 px-4 max-w-xs">
                      <div className="font-semibold text-gray-900 leading-tight">
                        {tx.description}
                      </div>
                      {tx.merchant_payee && (
                        <div className="text-xs text-gray-500 mt-0.5">{tx.merchant_payee}</div>
                      )}
                      {tx.notes && (
                        <div className="text-[11px] text-gray-400 italic mt-0.5 truncate">
                          Note: {tx.notes}
                        </div>
                      )}
                    </td>

                    <td className="py-3 px-4 text-xs text-gray-700 whitespace-nowrap">
                      <span className="font-medium">{tx.account_name || 'Account'}</span>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      {tx.category_name ? (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                          style={{
                            backgroundColor: `${tx.category_color || '#3b82f6'}15`,
                            color: tx.category_color || '#1e40af',
                          }}
                        >
                          {tx.category_name}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      {tx.source === 'demo_bank' ? (
                        <span className="px-2 py-0.5 bg-purple-50 text-purple-700 text-[10px] font-bold rounded-full border border-purple-200">
                          Demo Bank
                        </span>
                      ) : tx.source === 'csv_import' || tx.source === 'xlsx_import' ? (
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-[10px] font-bold rounded-full border border-blue-200 uppercase">
                          {tx.source === 'csv_import' ? 'CSV Import' : 'XLSX Import'}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-[10px] font-medium rounded-full">
                          Manual
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4 text-right font-bold whitespace-nowrap">
                      {tx.transaction_type === 'income' ? (
                        <span className="text-emerald-600 inline-flex items-center">
                          <ArrowDownLeft className="w-3.5 h-3.5 mr-0.5" />
                          +{formatINR(tx.amount)}
                        </span>
                      ) : tx.transaction_type === 'expense' ? (
                        <span className="text-rose-600 inline-flex items-center">
                          <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
                          -{formatINR(tx.amount)}
                        </span>
                      ) : (
                        <span className="text-blue-600 inline-flex items-center">
                          <ArrowRightLeft className="w-3.5 h-3.5 mr-0.5" />
                          {formatINR(tx.amount)}
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      {tx.transfer_id ? (
                        <span className="text-xs text-gray-400 italic">Transfer</span>
                      ) : (
                        <div className="flex items-center justify-end space-x-1">
                          <button
                            onClick={() => {
                              setEditingTx({ ...tx });
                              setFormError(null);
                            }}
                            className="p-1 text-gray-400 hover:text-blue-600 rounded"
                            title="Edit Transaction"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setDeletingTx(tx)}
                            className="p-1 text-gray-400 hover:text-red-600 rounded"
                            title="Delete Transaction"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between text-xs text-gray-600">
            <div>
              Showing <span className="font-semibold">{transactions.length}</span> of{' '}
              <span className="font-semibold">{total}</span> records (Page {page} of {totalPages})
            </div>
            <div className="flex items-center space-x-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2.5 py-1 rounded bg-white border border-gray-200 disabled:opacity-40 hover:bg-gray-100 flex items-center space-x-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Prev</span>
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-2.5 py-1 rounded bg-white border border-gray-200 disabled:opacity-40 hover:bg-gray-100 flex items-center space-x-1"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Record Transaction Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <button
              onClick={() => setIsAddModalOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-gray-900">Record Financial Transaction</h3>
            <p className="text-xs text-gray-500 mt-1">
              Posts an income or expense transaction with atomic double-entry ledger balancing.
            </p>

            {formError && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateTransaction} className="space-y-4 mt-4">
              {/* Type Switcher */}
              <div className="flex rounded-lg border border-gray-200 p-1 bg-gray-50">
                <button
                  type="button"
                  onClick={() =>
                    setFormData({
                      ...formData,
                      transaction_type: 'expense',
                      category_id: '',
                    })
                  }
                  className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                    formData.transaction_type === 'expense'
                      ? 'bg-rose-600 text-white shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Expense
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setFormData({
                      ...formData,
                      transaction_type: 'income',
                      category_id: '',
                    })
                  }
                  className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                    formData.transaction_type === 'income'
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Income
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Account *
                  </label>
                  <select
                    required
                    value={formData.account_id}
                    onChange={(e) => setFormData({ ...formData, account_id: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({formatINR(a.current_balance)})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Amount (₹) *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    placeholder="0.00"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Category</label>
                  <select
                    value={formData.category_id}
                    onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select Category</option>
                    {filteredCategoriesForForm.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Transaction Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={formData.transaction_date}
                    onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Description *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Swiggy food delivery, Salary credit"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Merchant / Payee
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Swiggy, Amazon India, Landlord"
                    value={formData.merchant_payee}
                    onChange={(e) => setFormData({ ...formData, merchant_payee: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Notes</label>
                  <input
                    type="text"
                    placeholder="Optional memo or reference"
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  />
                </div>
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm flex items-center space-x-1.5"
                >
                  {formSubmitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Save Transaction</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Transaction Modal */}
      {editingTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <button
              onClick={() => setEditingTx(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-gray-900">Edit Transaction</h3>
            <p className="text-xs text-gray-500 mt-1">
              Adjusting amount or date automatically updates ledger journal lines and synchronizes affected balances.
            </p>

            {formError && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {formError}
              </div>
            )}

            <form onSubmit={handleUpdateTransaction} className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Amount (₹) *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={editingTx.amount}
                    onChange={(e) => setEditingTx({ ...editingTx, amount: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={editingTx.transaction_date}
                    onChange={(e) =>
                      setEditingTx({ ...editingTx, transaction_date: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Description *
                </label>
                <input
                  type="text"
                  required
                  value={editingTx.description}
                  onChange={(e) => setEditingTx({ ...editingTx, description: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Category</label>
                  <select
                    value={editingTx.category_id || ''}
                    onChange={(e) =>
                      setEditingTx({ ...editingTx, category_id: e.target.value || null })
                    }
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  >
                    <option value="">No Category</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Merchant / Payee
                  </label>
                  <input
                    type="text"
                    value={editingTx.merchant_payee || ''}
                    onChange={(e) =>
                      setEditingTx({ ...editingTx, merchant_payee: e.target.value || null })
                    }
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Notes</label>
                <input
                  type="text"
                  value={editingTx.notes || ''}
                  onChange={(e) =>
                    setEditingTx({ ...editingTx, notes: e.target.value || null })
                  }
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                />
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setEditingTx(null)}
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

      {/* Delete Confirmation Modal */}
      {deletingTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <h3 className="text-base font-bold text-gray-900">Delete Transaction?</h3>
            <p className="text-xs text-gray-500 mt-2">
              Are you sure you want to delete &ldquo;{deletingTx.description}&rdquo; ({formatINR(deletingTx.amount)})?
              The ledger entry will be reversed and account balances updated.
            </p>

            {formError && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {formError}
              </div>
            )}

            <div className="mt-5 flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setDeletingTx(null)}
                className="px-4 py-2 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteTransaction}
                disabled={formSubmitting}
                className="px-4 py-2 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg shadow-sm"
              >
                Delete & Reverse
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
