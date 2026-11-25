import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Calculator,
  CheckCircle2,
  Percent,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  TrendingDown,
  X,
} from 'lucide-react';
import { loansApi } from '../../services/phase6Api';
import { financeApi } from '../../services/financeApi';
import { FinancialAccount, FinancialTransaction } from '../../types/finance';
import {
  CalculationMethod,
  EmiFrequency,
  InterestRateType,
  Loan,
  LoanInstallment,
  LoanPrepaymentScenario,
  LoanType,
} from '../../types/phase6';
import { formatDate, formatINR } from '../../lib/formatters';

export const LOAN_TYPES: { id: LoanType; label: string }[] = [
  { id: 'home', label: 'Home Loan' },
  { id: 'vehicle', label: 'Vehicle / Auto Loan' },
  { id: 'personal', label: 'Personal Loan' },
  { id: 'education', label: 'Education Loan' },
  { id: 'gold', label: 'Gold Loan' },
  { id: 'business', label: 'Business Loan' },
  { id: 'consumer_durable', label: 'Consumer Durable / No-Cost EMI' },
  { id: 'other', label: 'Other Loan' },
];

interface LoanFormModalProps {
  isOpen: boolean;
  editingLoan: Loan | null;
  accounts: FinancialAccount[];
  onClose: () => void;
  onSaved: (loan: Loan) => void;
}

export const LoanFormModal: React.FC<LoanFormModalProps> = ({
  isOpen,
  editingLoan,
  accounts,
  onClose,
  onSaved,
}) => {
  const [loanName, setLoanName] = useState('');
  const [lenderName, setLenderName] = useState('');
  const [loanType, setLoanType] = useState<LoanType>('personal');
  const [isExistingMidTenure, setIsExistingMidTenure] = useState(false);
  const [originalPrincipal, setOriginalPrincipal] = useState('');
  const [outstandingPrincipal, setOutstandingPrincipal] = useState('');
  const [interestRate, setInterestRate] = useState('10.50');
  const [rateType, setRateType] = useState<InterestRateType>('fixed');
  const [calcMethod, setCalcMethod] = useState<CalculationMethod>('reducing_balance');
  const [origTenure, setOrigTenure] = useState('36');
  const [remTenure, setRemTenure] = useState('36');
  const [emiOverride, setEmiOverride] = useState('');
  const [emiFreq, setEmiFreq] = useState<EmiFrequency>('monthly');
  const [loanStartDate, setLoanStartDate] = useState(new Date().toISOString().split('T')[0]);
  const [firstEmiDate, setFirstEmiDate] = useState(new Date().toISOString().split('T')[0]);
  const [repayAccountId, setRepayAccountId] = useState('');
  const [disbAccountId, setDisbAccountId] = useState('');
  const [loanRef, setLoanRef] = useState('');
  const [notes, setNotes] = useState('');
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    if (editingLoan) {
      setLoanName(editingLoan.loan_name);
      setLenderName(editingLoan.lender_name);
      setLoanType(editingLoan.loan_type);
      setRepayAccountId(editingLoan.linked_repayment_account_id || '');
      setLoanRef(editingLoan.loan_reference || '');
      setNotes(editingLoan.notes || '');
      setReminderEnabled(editingLoan.reminder_enabled);
    } else {
      const todayStr = new Date().toISOString().split('T')[0];
      setLoanName('');
      setLenderName('');
      setLoanType('personal');
      setIsExistingMidTenure(false);
      setOriginalPrincipal('');
      setOutstandingPrincipal('');
      setInterestRate('10.50');
      setRateType('fixed');
      setCalcMethod('reducing_balance');
      setOrigTenure('24');
      setRemTenure('24');
      setEmiOverride('');
      setEmiFreq('monthly');
      setLoanStartDate(todayStr);
      setFirstEmiDate(todayStr);
      setRepayAccountId('');
      setDisbAccountId('');
      setLoanRef('');
      setNotes('');
      setReminderEnabled(true);
    }
  }, [isOpen, editingLoan]);

  if (!isOpen) return null;

  const assetAccounts = accounts.filter(
    (a) => a.account_type !== 'credit_card' && a.account_type !== 'loan_liability'
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      let saved: Loan;
      if (editingLoan) {
        saved = await loansApi.updateLoan(editingLoan.id, {
          loan_name: loanName.trim(),
          lender_name: lenderName.trim(),
          loan_type: loanType,
          linked_repayment_account_id: repayAccountId || null,
          loan_reference: loanRef.trim() || null,
          notes: notes.trim() || null,
          reminder_enabled: reminderEnabled,
        });
      } else {
        const outP = Number(outstandingPrincipal);
        if (!outstandingPrincipal || isNaN(outP) || outP <= 0) {
          throw new Error('Outstanding principal must be positive.');
        }
        const todayStr = new Date().toISOString().split('T')[0];
        saved = await loansApi.createLoan({
          loan_name: loanName.trim(),
          lender_name: lenderName.trim(),
          loan_type: loanType,
          original_principal: originalPrincipal ? Number(originalPrincipal).toFixed(2) : null,
          outstanding_principal: outP.toFixed(2),
          interest_rate:
            calcMethod === 'zero_interest' ? '0.000' : Number(interestRate || 0).toFixed(3),
          interest_rate_type: rateType,
          calculation_method: calcMethod,
          loan_start_date: loanStartDate,
          tracking_start_date: todayStr,
          first_emi_date: firstEmiDate,
          original_tenure_months: origTenure ? Number(origTenure) : null,
          remaining_tenure_months: Number(remTenure || 12),
          emi_amount: emiOverride ? Number(emiOverride).toFixed(2) : null,
          emi_frequency: emiFreq,
          linked_repayment_account_id: repayAccountId || null,
          record_disbursement_to_account_id:
            !isExistingMidTenure && disbAccountId ? disbAccountId : null,
          loan_reference: loanRef.trim() || null,
          notes: notes.trim() || null,
          reminder_enabled: reminderEnabled,
        });
      }
      onSaved(saved);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save loan.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl relative max-h-[92vh] overflow-y-auto text-xs">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>

        <h3 className="text-lg font-bold text-gray-900">
          {editingLoan ? 'Edit Loan Metadata' : 'Register New or Existing Loan'}
        </h3>
        <p className="text-gray-500 mt-0.5">
          Creates a linked loan liability account cleanly tracked inside your double-entry ledger.
        </p>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5 mt-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Loan Name *</label>
              <input
                type="text"
                required
                placeholder="e.g., HDFC Home Loan"
                value={loanName}
                onChange={(e) => setLoanName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Lender / Bank *</label>
              <input
                type="text"
                required
                placeholder="e.g., HDFC Bank, SBI"
                value={lenderName}
                onChange={(e) => setLenderName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Loan Type</label>
              <select
                aria-label="Loan Type"
                value={loanType}
                onChange={(e) => setLoanType(e.target.value as LoanType)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                {LOAN_TYPES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {!editingLoan && (
            <>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                <label className="flex items-center space-x-2 cursor-pointer font-semibold text-gray-800">
                  <input
                    type="checkbox"
                    checked={isExistingMidTenure}
                    onChange={(e) => setIsExistingMidTenure(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600"
                  />
                  <span>Already-Existing Mid-Tenure Loan (Enter current remaining principal &amp; tenure)</span>
                </label>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    {isExistingMidTenure ? 'Current Outstanding Principal (₹) *' : 'Loan Principal (₹) *'}
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    placeholder="e.g., 500000.00"
                    value={outstandingPrincipal}
                    onChange={(e) => setOutstandingPrincipal(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Original Principal (Optional ₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="If already partially paid"
                    value={originalPrincipal}
                    onChange={(e) => setOriginalPrincipal(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Annual Interest Rate (% p.a.)
                  </label>
                  <input
                    type="number"
                    step="0.001"
                    min="0"
                    disabled={calcMethod === 'zero_interest'}
                    value={calcMethod === 'zero_interest' ? '0' : interestRate}
                    onChange={(e) => setInterestRate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Calculation Method</label>
                  <select
                    aria-label="Calculation Method"
                    value={calcMethod}
                    onChange={(e) => setCalcMethod(e.target.value as CalculationMethod)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
                  >
                    <option value="reducing_balance">Reducing Balance</option>
                    <option value="flat_rate">Flat Rate</option>
                    <option value="zero_interest">Zero Interest (0%)</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Rate Type</label>
                  <select
                    value={rateType}
                    onChange={(e) => setRateType(e.target.value as InterestRateType)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
                  >
                    <option value="fixed">Fixed</option>
                    <option value="floating">Floating</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Remaining Installments *
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={remTenure}
                    onChange={(e) => setRemTenure(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Known EMI (Optional ₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="Auto-calculated if blank"
                    value={emiOverride}
                    onChange={(e) => setEmiOverride(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Loan Start Date</label>
                  <input
                    type="date"
                    required
                    value={loanStartDate}
                    onChange={(e) => setLoanStartDate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    {isExistingMidTenure ? 'Next Upcoming EMI Date *' : 'First EMI Date *'}
                  </label>
                  <input
                    type="date"
                    required
                    value={firstEmiDate}
                    onChange={(e) => setFirstEmiDate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">EMI Frequency</label>
                  <select
                    value={emiFreq}
                    onChange={(e) => setEmiFreq(e.target.value as EmiFrequency)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="weekly">Weekly</option>
                  </select>
                </div>
              </div>

              {!isExistingMidTenure && (
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">
                    Credit Disbursement to Bank Account (Optional — recorded as borrowed transfer, NOT income)
                  </label>
                  <select
                    value={disbAccountId}
                    onChange={(e) => setDisbAccountId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
                  >
                    <option value="">Do not credit any bank account (Opening liability only)</option>
                    {assetAccounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({formatINR(a.current_balance)})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Default Repayment Account
              </label>
              <select
                value={repayAccountId}
                onChange={(e) => setRepayAccountId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="">Select at repayment time</option>
                {assetAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({formatINR(a.current_balance)})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Loan Account Ref</label>
              <input
                type="text"
                value={loanRef}
                onChange={(e) => setLoanRef(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="checkbox"
              checked={reminderEnabled}
              onChange={(e) => setReminderEnabled(e.target.checked)}
              className="rounded border-gray-300 text-indigo-600"
            />
            <span className="font-semibold text-gray-800">
              Enable EMI Due Reminders (Shared Phase 5 Reminder Engine)
            </span>
          </label>

          <div className="flex justify-end space-x-2 pt-3 border-t border-gray-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-100 rounded-lg text-gray-700 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold inline-flex items-center space-x-1"
            >
              {submitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
              <span>{editingLoan ? 'Save Metadata' : 'Create Loan'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface LoanPaymentModalProps {
  loan: Loan | null;
  installment?: LoanInstallment | null;
  presetPrepayment?: { principal: string; mode: 'reduce_tenure' | 'reduce_emi'; fee: string } | null;
  accounts: FinancialAccount[];
  onClose: () => void;
  onRecorded: (updated: Loan) => void;
}

export const LoanPaymentModal: React.FC<LoanPaymentModalProps> = ({
  loan,
  installment,
  presetPrepayment,
  accounts,
  onClose,
  onRecorded,
}) => {
  const [payType, setPayType] = useState<'emi' | 'partial' | 'prepayment' | 'foreclosure'>('emi');
  const [principalPaid, setPrincipalPaid] = useState('');
  const [interestPaid, setInterestPaid] = useState('0.00');
  const [feePaid, setFeePaid] = useState('0.00');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [accountId, setAccountId] = useState('');
  const [prepayMode, setPrepayMode] = useState<'reduce_tenure' | 'reduce_emi'>('reduce_tenure');
  const [ref, setRef] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idemKey, setIdemKey] = useState('');

  useEffect(() => {
    if (!loan) return;
    setError(null);
    setIdemKey(`loanpay-${loan.id}-${Date.now()}`);
    setPaymentDate(new Date().toISOString().split('T')[0]);
    const validAccs = accounts.filter((a) => a.account_type !== 'loan_liability');
    setAccountId(loan.linked_repayment_account_id || validAccs[0]?.id || '');
    setRef('');
    setNotes('');

    if (presetPrepayment) {
      setPayType('prepayment');
      setPrincipalPaid(presetPrepayment.principal);
      setInterestPaid('0.00');
      setFeePaid(presetPrepayment.fee || '0.00');
      setPrepayMode(presetPrepayment.mode);
    } else {
      const targetInst =
        installment ||
        loan.installments.find((i) => i.status === 'upcoming' || i.status === 'partially_paid');
      setPayType('emi');
      if (targetInst) {
        const remP = Math.max(
          0,
          Number(targetInst.principal_component) - Number(targetInst.principal_paid || 0)
        );
        const remI = Math.max(
          0,
          Number(targetInst.interest_component) - Number(targetInst.interest_paid || 0)
        );
        setPrincipalPaid(remP.toFixed(2));
        setInterestPaid(remI.toFixed(2));
      } else {
        setPrincipalPaid(String(loan.current_outstanding_principal));
        setInterestPaid('0.00');
      }
      setFeePaid('0.00');
    }
  }, [loan, installment, presetPrepayment, accounts]);

  if (!loan) return null;

  const totalOutflow =
    (parseFloat(principalPaid || '0') || 0) +
    (parseFloat(interestPaid || '0') || 0) +
    (parseFloat(feePaid || '0') || 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await loansApi.recordPayment(loan.id, {
        payment_type: payType,
        payment_date: paymentDate,
        payment_account_id: accountId,
        installment_id: payType === 'emi' || payType === 'partial' ? installment?.id || undefined : undefined,
        principal_paid: Number(principalPaid || 0).toFixed(2),
        interest_paid: Number(interestPaid || 0).toFixed(2),
        fee_paid: Number(feePaid || 0).toFixed(2),
        prepayment_mode: prepayMode,
        reference_number: ref.trim() || undefined,
        notes: notes.trim() || undefined,
        idempotency_key: idemKey,
      });
      onRecorded(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to record loan payment.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl relative text-xs">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>

        <h3 className="text-lg font-bold text-gray-900">Record Loan Repayment</h3>
        <p className="text-gray-500 mt-0.5">
          {loan.loan_name} • Remaining Principal:{' '}
          <strong>{formatINR(loan.current_outstanding_principal)}</strong>
        </p>

        <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-xl text-[11px] text-blue-900 flex items-start space-x-2">
          <ShieldAlert className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <span>
            <strong>Split Accounting Integrity:</strong> Principal reduction posts as a liability
            transfer (NOT an expense), while Interest posts as an actual Loan Interest expense. No
            automated bank debits are executed.
          </span>
        </div>

        {error && (
          <div className="mt-3 p-2.5 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3 mt-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Repayment Type</label>
              <select
                aria-label="Repayment Type"
                value={payType}
                onChange={(e) => {
                  const v = e.target.value as 'emi' | 'partial' | 'prepayment' | 'foreclosure';
                  setPayType(v);
                  if (v === 'foreclosure') {
                    setPrincipalPaid(String(loan.current_outstanding_principal));
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="emi">Scheduled EMI</option>
                <option value="partial">Partial Repayment</option>
                <option value="prepayment">Principal Prepayment</option>
                <option value="foreclosure">Full Foreclosure</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Payment Date</label>
              <input
                type="date"
                required
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Principal Paid (₹)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                required
                value={principalPaid}
                onChange={(e) => setPrincipalPaid(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Interest Paid (₹)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                required
                value={interestPaid}
                onChange={(e) => setInterestPaid(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Fee (Optional ₹)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={feePaid}
                onChange={(e) => setFeePaid(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>
          </div>

          {payType === 'prepayment' && (
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Post-Prepayment Schedule Adjustment
              </label>
              <select
                value={prepayMode}
                onChange={(e) => setPrepayMode(e.target.value as 'reduce_tenure' | 'reduce_emi')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="reduce_tenure">Keep EMI Same &amp; Reduce Remaining Tenure</option>
                <option value="reduce_emi">Keep Tenure Same &amp; Reduce EMI</option>
              </select>
            </div>
          )}

          <div>
            <label className="block font-semibold text-gray-700 mb-1">Payment Account *</label>
            <select
              required
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
            >
              {accounts
                .filter((a) => a.account_type !== 'loan_liability')
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({formatINR(a.current_balance)})
                  </option>
                ))}
            </select>
          </div>

          <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex justify-between font-semibold">
            <span>Total Bank Outflow:</span>
            <span className="text-gray-900">{formatINR(totalOutflow.toFixed(2))}</span>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-gray-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-100 rounded-lg text-gray-700 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold inline-flex items-center space-x-1"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Confirm Repayment</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface LoanDetailsModalProps {
  loan: Loan | null;
  accounts: FinancialAccount[];
  onClose: () => void;
  onEdit: (l: Loan) => void;
  onRecordPayment: (
    l: Loan,
    inst?: LoanInstallment | null,
    preset?: { principal: string; mode: 'reduce_tenure' | 'reduce_emi'; fee: string }
  ) => void;
  onUpdated: (l: Loan) => void;
}

export const LoanDetailsModal: React.FC<LoanDetailsModalProps> = ({
  loan,
  onClose,
  onEdit,
  onRecordPayment,
  onUpdated,
}) => {
  const [innerTab, setInnerTab] = useState<'schedule' | 'payments' | 'rate' | 'prepay'>('schedule');
  const [newRate, setNewRate] = useState('');
  const [ratePolicy, setRatePolicy] = useState<'recalculate_emi' | 'adjust_tenure'>('recalculate_emi');
  const [rateReason, setRateReason] = useState('');
  const [extraMonthly, setExtraMonthly] = useState('0');
  const [lumpSum, setLumpSum] = useState('0');
  const [prepayMode, setPrepayMode] = useState<'reduce_tenure' | 'reduce_emi'>('reduce_tenure');
  const [userFee, setUserFee] = useState('0');
  const [scenario, setScenario] = useState<LoanPrepaymentScenario | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [showLinkTx, setShowLinkTx] = useState(false);
  const [txList, setTxList] = useState<FinancialTransaction[]>([]);
  const [selectedTxId, setSelectedTxId] = useState('');
  const [linkPrin, setLinkPrin] = useState('');
  const [linkInt, setLinkInt] = useState('0.00');

  useEffect(() => {
    if (!loan) return;
    setNewRate(String(loan.interest_rate));
    setScenario(null);
    setErr(null);
    setShowLinkTx(false);
  }, [loan]);

  if (!loan) return null;

  const handleRateRevision = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const updated = await loansApi.reviseRate(loan.id, {
        new_rate: Number(newRate).toFixed(3),
        effective_date: new Date().toISOString().split('T')[0],
        policy: ratePolicy,
        reason: rateReason.trim() || undefined,
      });
      onUpdated(updated);
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : 'Rate revision failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleSimulatePrepay = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = await loansApi.simulatePrepayment(loan.id, {
        extra_monthly_emi: Number(extraMonthly || 0).toFixed(2),
        lump_sum_prepayment: Number(lumpSum || 0).toFixed(2),
        prepayment_mode: prepayMode,
        user_prepayment_fee: Number(userFee || 0).toFixed(2),
      });
      setScenario(res);
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : 'Simulation failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-2xl max-w-4xl w-full p-6 shadow-xl relative max-h-[92vh] overflow-y-auto text-xs space-y-4">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex flex-wrap justify-between items-start gap-3 pr-8">
          <div>
            <h3 className="text-lg font-bold text-gray-900">{loan.loan_name}</h3>
            <p className="text-gray-500">
              {loan.lender_name} • {loan.interest_rate}% ({loan.interest_rate_type} •{' '}
              {loan.calculation_method.replace('_', ' ')})
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {loan.status !== 'closed' && loan.status !== 'archived' && (
              <button
                type="button"
                onClick={() => onRecordPayment(loan, null)}
                className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg font-semibold"
              >
                Record EMI / Prepayment
              </button>
            )}
            <button
              type="button"
              onClick={() => onEdit(loan)}
              className="px-3 py-1.5 bg-gray-100 text-gray-800 rounded-lg font-medium"
            >
              Edit
            </button>
          </div>
        </div>

        {err && <div className="p-2.5 bg-red-50 border border-red-200 rounded text-red-700">{err}</div>}

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
          <div>
            <div className="text-gray-500">Outstanding Principal</div>
            <div className="font-bold text-rose-700">{formatINR(loan.current_outstanding_principal)}</div>
          </div>
          <div>
            <div className="text-gray-500">Current EMI</div>
            <div className="font-bold text-gray-900">{formatINR(loan.emi_amount)}</div>
          </div>
          <div>
            <div className="text-gray-500">Principal Repaid</div>
            <div className="font-bold text-emerald-700">{formatINR(loan.total_principal_repaid)}</div>
          </div>
          <div>
            <div className="text-gray-500">Interest Paid</div>
            <div className="font-bold text-amber-700">{formatINR(loan.total_interest_paid)}</div>
          </div>
          <div>
            <div className="text-gray-500">Maturity / Progress</div>
            <div className="font-bold text-indigo-700">
              {loan.maturity_date ? formatDate(loan.maturity_date) : 'Closed'} ({loan.repayment_progress_pct}%)
            </div>
          </div>
        </div>

        <div className="border-b border-gray-200 flex space-x-2">
          {[
            { id: 'schedule', label: `Amortization Schedule (${loan.installments.length})` },
            { id: 'payments', label: `Repayment History (${loan.payments.length})` },
            { id: 'rate', label: `Interest Rate History (${loan.rate_history.length})` },
            { id: 'prepay', label: 'Prepayment Simulator' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setInnerTab(t.id as 'schedule' | 'payments' | 'rate' | 'prepay')}
              className={`px-3 py-2 font-semibold border-b-2 ${
                innerTab === t.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {innerTab === 'schedule' && (
          <div className="max-h-72 overflow-y-auto border border-gray-200 rounded-xl">
            <table className="w-full text-left text-[11px]">
              <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 sticky top-0">
                <tr>
                  <th className="py-2 px-3">#</th>
                  <th className="py-2 px-3">Due Date</th>
                  <th className="py-2 px-3 text-right">Opening</th>
                  <th className="py-2 px-3 text-right">EMI</th>
                  <th className="py-2 px-3 text-right">Principal</th>
                  <th className="py-2 px-3 text-right">Interest</th>
                  <th className="py-2 px-3 text-right">Closing</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loan.installments.map((inst) => (
                  <tr key={inst.id}>
                    <td className="py-2 px-3">{inst.installment_number}</td>
                    <td className="py-2 px-3">{formatDate(inst.due_date)}</td>
                    <td className="py-2 px-3 text-right">{formatINR(inst.opening_principal)}</td>
                    <td className="py-2 px-3 text-right font-semibold">{formatINR(inst.emi_amount)}</td>
                    <td className="py-2 px-3 text-right text-emerald-700">
                      {formatINR(inst.principal_component)}
                    </td>
                    <td className="py-2 px-3 text-right text-amber-700">
                      {formatINR(inst.interest_component)}
                    </td>
                    <td className="py-2 px-3 text-right">{formatINR(inst.closing_principal)}</td>
                    <td className="py-2 px-3 uppercase font-bold">{inst.derived_status}</td>
                    <td className="py-2 px-3 text-right">
                      {inst.status !== 'paid' && loan.status !== 'closed' && (
                        <button
                          type="button"
                          onClick={() => onRecordPayment(loan, inst)}
                          className="text-emerald-700 hover:underline font-semibold"
                        >
                          Pay
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {innerTab === 'payments' && (
          <div className="space-y-3">
            <div className="flex justify-end">
              {loan.status !== 'closed' && (
                <button
                  type="button"
                  onClick={async () => {
                    setShowLinkTx(true);
                    const res = await financeApi.listTransactions({ page: 1, page_size: 20 });
                    setTxList(res.items);
                    if (res.items[0]) {
                      setSelectedTxId(res.items[0].id);
                      setLinkPrin(String(res.items[0].amount));
                    }
                  }}
                  className="text-blue-600 hover:underline font-medium"
                >
                  + Link Existing Transaction
                </button>
              )}
            </div>
            {showLinkTx && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg space-y-2">
                <select
                  value={selectedTxId}
                  onChange={(e) => setSelectedTxId(e.target.value)}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-white"
                >
                  {txList.map((t) => (
                    <option key={t.id} value={t.id}>
                      {formatDate(t.transaction_date)} — {t.description} ({formatINR(t.amount)})
                    </option>
                  ))}
                </select>
                <div className="flex gap-2">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Principal ₹"
                    value={linkPrin}
                    onChange={(e) => setLinkPrin(e.target.value)}
                    className="px-2.5 py-1.5 border border-gray-300 rounded"
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Interest ₹"
                    value={linkInt}
                    onChange={(e) => setLinkInt(e.target.value)}
                    className="px-2.5 py-1.5 border border-gray-300 rounded"
                  />
                  <button
                    type="button"
                    onClick={async () => {
                      const updated = await loansApi.linkTransaction(loan.id, {
                        transaction_id: selectedTxId,
                        principal_component: Number(linkPrin || 0).toFixed(2),
                        interest_component: Number(linkInt || 0).toFixed(2),
                      });
                      onUpdated(updated);
                      setShowLinkTx(false);
                    }}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded font-semibold"
                  >
                    Link Split
                  </button>
                </div>
              </div>
            )}

            {loan.payments.map((p) => (
              <div
                key={p.id}
                className="p-3 border border-gray-200 rounded-xl flex items-center justify-between"
              >
                <div>
                  <span className="font-bold">{formatINR(p.total_paid)}</span> ({p.payment_type.toUpperCase()})
                  on {formatDate(p.payment_date)} • Principal: {formatINR(p.principal_paid)}, Interest:{' '}
                  {formatINR(p.interest_paid)}
                  {p.payment_status === 'reversed' && (
                    <span className="ml-2 px-1.5 py-0.5 bg-rose-50 text-rose-700 rounded text-[10px] font-bold">
                      REVERSED
                    </span>
                  )}
                </div>
                {p.payment_status === 'completed' && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={async () => {
                      const reason = window.prompt('Reason for reversing repayment:') || '';
                      if (reason.trim().length >= 2) {
                        const updated = await loansApi.reversePayment(loan.id, p.id, reason.trim());
                        onUpdated(updated);
                      }
                    }}
                    className="text-rose-600 hover:underline inline-flex items-center space-x-1"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Reverse</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {innerTab === 'rate' && (
          <div className="space-y-4">
            {loan.status !== 'closed' && (
              <form onSubmit={handleRateRevision} className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                <input
                  type="number"
                  step="0.001"
                  min="0"
                  placeholder="New Rate %"
                  value={newRate}
                  onChange={(e) => setNewRate(e.target.value)}
                  className="px-2.5 py-2 border border-gray-300 rounded font-mono"
                />
                <select
                  value={ratePolicy}
                  onChange={(e) =>
                    setRatePolicy(e.target.value as 'recalculate_emi' | 'adjust_tenure')
                  }
                  className="px-2.5 py-2 border border-gray-300 rounded bg-white"
                >
                  <option value="recalculate_emi">Recalculate EMI (Keep Tenure)</option>
                  <option value="adjust_tenure">Adjust Tenure (Keep EMI)</option>
                </select>
                <input
                  type="text"
                  placeholder="Reason (e.g. Repo hike)"
                  value={rateReason}
                  onChange={(e) => setRateReason(e.target.value)}
                  className="px-2.5 py-2 border border-gray-300 rounded"
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="px-3 py-2 bg-indigo-600 text-white rounded font-semibold inline-flex items-center justify-center space-x-1"
                >
                  <Percent className="w-3.5 h-3.5" />
                  <span>Revise Future Rate</span>
                </button>
              </form>
            )}
            <div className="divide-y divide-gray-100 border border-gray-200 rounded-xl">
              {loan.rate_history.map((h) => (
                <div key={h.id} className="p-2.5 flex justify-between">
                  <span>
                    {formatDate(h.effective_date)}:{' '}
                    {h.previous_rate ? `${h.previous_rate}% → ` : 'Initial '}
                    <strong>{h.new_rate}%</strong> (EMI: {formatINR(h.new_emi)})
                  </span>
                  <span className="text-gray-400">{h.reason || ''}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {innerTab === 'prepay' && (
          <div className="space-y-4">
            <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-indigo-900 flex items-center space-x-2">
              <Calculator className="w-4 h-4 text-indigo-600 flex-shrink-0" />
              <span>
                <strong>Scenario Mode Only:</strong> Calculations below do NOT modify PostgreSQL
                loan balances or ledger until you confirm an actual prepayment.
              </span>
            </div>
            <form onSubmit={handleSimulatePrepay} className="grid grid-cols-1 sm:grid-cols-5 gap-2">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">One-Time Lump Sum (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={lumpSum}
                  onChange={(e) => setLumpSum(e.target.value)}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Extra Monthly EMI (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={extraMonthly}
                  onChange={(e) => setExtraMonthly(e.target.value)}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">User Fee (Optional ₹)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={userFee}
                  onChange={(e) => setUserFee(e.target.value)}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Impact Mode</label>
                <select
                  value={prepayMode}
                  onChange={(e) =>
                    setPrepayMode(e.target.value as 'reduce_tenure' | 'reduce_emi')
                  }
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded bg-white"
                >
                  <option value="reduce_tenure">Reduce Tenure</option>
                  <option value="reduce_emi">Reduce EMI</option>
                </select>
              </div>
              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full px-3 py-1.5 bg-blue-600 text-white rounded font-semibold"
                >
                  Simulate Savings
                </button>
              </div>
            </form>

            {scenario && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-emerald-900 flex items-center space-x-1.5">
                    <TrendingDown className="w-4 h-4" />
                    <span>Hypothetical Prepayment Result (Unconfirmed)</span>
                  </span>
                  {Number(lumpSum || 0) > 0 && loan.status !== 'closed' && (
                    <button
                      type="button"
                      onClick={() =>
                        onRecordPayment(loan, null, {
                          principal: Number(lumpSum).toFixed(2),
                          mode: prepayMode,
                          fee: Number(userFee || 0).toFixed(2),
                        })
                      }
                      className="px-3 py-1.5 bg-emerald-700 text-white rounded-lg font-semibold"
                    >
                      Apply as Confirmed Prepayment
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
                  <div>
                    <div className="text-emerald-700">Est. Interest Saved</div>
                    <div className="font-bold text-emerald-900">
                      {formatINR(scenario.estimated_interest_saved)}
                    </div>
                  </div>
                  <div>
                    <div className="text-emerald-700">Net Savings (After Fee)</div>
                    <div className="font-bold text-emerald-900">
                      {formatINR(scenario.net_estimated_savings)}
                    </div>
                  </div>
                  <div>
                    <div className="text-emerald-700">Revised EMI / Months</div>
                    <div className="font-bold text-emerald-900">
                      {formatINR(scenario.scenario_revised_emi)} ({scenario.scenario_remaining_installments} left)
                    </div>
                  </div>
                  <div>
                    <div className="text-emerald-700">Months Saved</div>
                    <div className="font-bold text-emerald-900">{scenario.tenure_months_saved}</div>
                  </div>
                </div>
                <p className="text-[11px] text-emerald-800">{scenario.disclaimer}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
