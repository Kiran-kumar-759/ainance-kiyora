import React, { useState, useEffect } from 'react';
import {
  ArrowRightLeft,
  RefreshCw,
  AlertCircle,
  RotateCcw,
  CheckCircle2,
  X,
  Wallet,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import { FinancialAccount, FinancialTransfer } from '../../types/finance';
import { formatINR, formatDate } from '../../lib/formatters';

interface TransfersPageProps {
  onNavigate: (view: string) => void;
}

export const TransfersPage: React.FC<TransfersPageProps> = ({ onNavigate }) => {
  const [transfers, setTransfers] = useState<FinancialTransfer[]>([]);
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Transfer form state
  const [sourceAccountId, setSourceAccountId] = useState<string>('');
  const [destAccountId, setDestAccountId] = useState<string>('');
  const [amount, setAmount] = useState<string>('');
  const [transferDate, setTransferDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [description, setDescription] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Reversal modal
  const [reversingTransfer, setReversingTransfer] = useState<FinancialTransfer | null>(null);
  const [reversalReason, setReversalReason] = useState<string>('Accidental transfer');
  const [isReversing, setIsReversing] = useState<boolean>(false);
  const [reversalError, setReversalError] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [accList, trList] = await Promise.all([
        financeApi.listAccounts(false),
        financeApi.listTransfers(50),
      ]);
      setAccounts(accList);
      setTransfers(trList);
      if (accList.length >= 2 && !sourceAccountId && !destAccountId) {
        setSourceAccountId(accList[0].id);
        setDestAccountId(accList[1].id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load transfer data.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleExecuteTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setFormError(null);
    setSuccessMessage(null);

    if (!sourceAccountId || !destAccountId) {
      setFormError('Please select both source and destination accounts.');
      return;
    }
    if (sourceAccountId === destAccountId) {
      setFormError('Source and destination accounts cannot be the same.');
      return;
    }
    const numAmt = parseFloat(amount);
    if (isNaN(numAmt) || numAmt <= 0) {
      setFormError('Transfer amount must be greater than zero.');
      return;
    }
    const srcAcc = accounts.find((a) => a.id === sourceAccountId);
    if (srcAcc && srcAcc.account_type !== 'credit_card' && numAmt > Number(srcAcc.current_balance)) {
      setFormError(
        `Insufficient balance in ${srcAcc.name}. Available balance is ${formatINR(srcAcc.current_balance)}.`
      );
      return;
    }

    setIsSubmitting(true);
    try {
      await financeApi.executeTransfer({
        source_account_id: sourceAccountId,
        destination_account_id: destAccountId,
        amount,
        transfer_date: transferDate,
        description: description.trim() || undefined,
      });

      setSuccessMessage('Transfer executed successfully!');
      setAmount('');
      setDescription('');
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to execute transfer.';
      setFormError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmReversal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reversingTransfer || isReversing) return;

    setIsReversing(true);
    setReversalError(null);
    try {
      await financeApi.reverseTransfer(reversingTransfer.id, reversalReason.trim());
      setReversingTransfer(null);
      await loadData();
      setSuccessMessage('Transfer reversed and account balances restored.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reverse transfer.';
      setReversalError(msg);
    } finally {
      setIsReversing(false);
    }
  };

  const sourceAccount = accounts.find((a) => a.id === sourceAccountId);
  const destAccount = accounts.find((a) => a.id === destAccountId);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Fund Transfers</h1>
        <p className="text-sm text-gray-600 mt-1">
          Move money atomically between your financial accounts or pay credit card bills with dual ledger journal entries.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid: Transfer Form (Left) & Transfer History (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Transfer Form Box */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm h-fit">
          <div className="flex items-center space-x-2 pb-4 border-b border-gray-100">
            <ArrowRightLeft className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-semibold text-gray-900">Execute Money Transfer</h2>
          </div>

          {formError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
              <span>{formError}</span>
            </div>
          )}

          {successMessage && (
            <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
              <span>{successMessage}</span>
            </div>
          )}

          {accounts.length < 2 ? (
            <div className="py-8 text-center text-gray-500 text-sm space-y-3">
              <Wallet className="w-10 h-10 mx-auto text-gray-300" />
              <p>You need at least two active accounts to perform a transfer.</p>
              <div className="flex flex-wrap justify-center gap-2">
                <button
                  type="button"
                  onClick={() => onNavigate('banking')}
                  className="px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 text-xs font-semibold"
                >
                  Connect Bank Account
                </button>
                <button
                  type="button"
                  onClick={() => onNavigate('accounts')}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 text-xs font-semibold"
                >
                  + Add Another Account
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleExecuteTransfer} className="space-y-4 mt-4">
              {/* Source Account */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  From Account (Source) *
                </label>
                <select
                  required
                  value={sourceAccountId}
                  onChange={(e) => setSourceAccountId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id} disabled={a.id === destAccountId}>
                      {a.name} ({formatINR(a.current_balance)})
                    </option>
                  ))}
                </select>
              </div>

              {/* Destination Account */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  To Account (Destination) *
                </label>
                <select
                  required
                  value={destAccountId}
                  onChange={(e) => setDestAccountId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id} disabled={a.id === sourceAccountId}>
                      {a.name} ({formatINR(a.current_balance)})
                    </option>
                  ))}
                </select>
              </div>

              {/* Amount & Date */}
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
                    placeholder="0.00"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Transfer Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={transferDate}
                    onChange={(e) => setTransferDate(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Description / Memo
                </label>
                <input
                  type="text"
                  placeholder="e.g. Credit Card bill payment, Wallet load"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Transfer Preview Card */}
              {amount && !isNaN(parseFloat(amount)) && parseFloat(amount) > 0 && (
                <div className="p-3 bg-blue-50/70 border border-blue-100 rounded-lg text-xs text-blue-900 space-y-1">
                  <div className="font-semibold text-blue-800">Transfer Summary:</div>
                  <div className="flex items-center justify-between">
                    <span>Amount:</span>
                    <span className="font-bold">{formatINR(amount)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>From:</span>
                    <span>{sourceAccount?.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>To:</span>
                    <span>{destAccount?.name}</span>
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg shadow-sm transition-colors flex items-center justify-center space-x-1.5"
              >
                {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                <span>Transfer Funds</span>
              </button>
            </form>
          )}
        </div>

        {/* Transfer History (Right 2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center justify-between pb-4 border-b border-gray-100">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Transfer History</h2>
              <p className="text-xs text-gray-500">
                Audit trail of completed transfers and ledger balance reversals.
              </p>
            </div>
            <button
              onClick={loadData}
              disabled={isLoading}
              className="p-1.5 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100"
              title="Refresh History"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div className="mt-4">
            {isLoading ? (
              <div className="p-8 text-center text-gray-400">Loading transfers...</div>
            ) : transfers.length === 0 ? (
              <div className="p-12 text-center text-gray-400">
                <ArrowRightLeft className="w-10 h-10 mx-auto mb-2 text-gray-300" />
                <p className="text-sm">No transfers executed yet.</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {transfers.map((tr) => (
                  <div
                    key={tr.id}
                    className="py-3.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-gray-50/70 p-2 rounded-lg transition-colors"
                  >
                    <div className="flex items-start space-x-3">
                      <div
                        className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${
                          tr.status === 'reversed'
                            ? 'bg-amber-50 text-amber-600'
                            : 'bg-blue-50 text-blue-600'
                        }`}
                      >
                        <ArrowRightLeft className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-gray-900">
                          {tr.source_account_name || 'Source'} &rarr;{' '}
                          {tr.destination_account_name || 'Destination'}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5">
                          {tr.description || 'Account Transfer'} • {formatDate(tr.transfer_date)}
                        </div>
                        {tr.status === 'reversed' && (
                          <div className="text-[11px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 mt-1 inline-block">
                            Reversed: {tr.reversal_reason || 'Reversed by user'}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center">
                      <div className="text-sm font-bold text-gray-900">
                        {formatINR(tr.amount)}
                      </div>

                      {tr.status === 'completed' && (
                        <button
                          onClick={() => {
                            setReversingTransfer(tr);
                            setReversalReason('Accidental transfer');
                          }}
                          className="mt-1 text-xs text-red-600 hover:text-red-800 font-medium flex items-center space-x-1"
                          title="Reverse Transfer"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Reverse</span>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Reversal Confirmation Modal */}
      {reversingTransfer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <button
              onClick={() => setReversingTransfer(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-bold text-gray-900">Reverse Fund Transfer?</h3>
            <p className="text-xs text-gray-500 mt-2">
              Reversing {formatINR(reversingTransfer.amount)} between{' '}
              {reversingTransfer.source_account_name} and{' '}
              {reversingTransfer.destination_account_name} will restore both original account balances.
            </p>

            {reversalError && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {reversalError}
              </div>
            )}

            <form onSubmit={handleConfirmReversal} className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Reason for Reversal *
                </label>
                <input
                  type="text"
                  required
                  value={reversalReason}
                  onChange={(e) => setReversalReason(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setReversingTransfer(null)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isReversing}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg shadow-sm flex items-center space-x-1"
                >
                  {isReversing && <RefreshCw className="w-3 h-3 animate-spin" />}
                  <span>Confirm Reversal</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
