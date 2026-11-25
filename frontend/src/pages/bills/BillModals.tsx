import React, { useState, useEffect } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileText,
  Info,
  Link2,
  Paperclip,
  RefreshCw,
  ShieldAlert,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { billsApi } from '../../services/billsApi';
import { financeApi } from '../../services/financeApi';
import {
  Bill,
  BillCategory,
  BillFrequency,
  BillType,
  PaymentMethod,
} from '../../types/bills';
import {
  FinancialAccount,
  FinancialCategory,
  FinancialTransaction,
} from '../../types/finance';
import { formatDate, formatINR } from '../../lib/formatters';

export const BILL_CATEGORIES: { id: BillCategory; label: string }[] = [
  { id: 'electricity', label: 'Electricity Bill' },
  { id: 'water', label: 'Water Bill' },
  { id: 'gas', label: 'Gas / PNG' },
  { id: 'internet', label: 'Internet & Broadband' },
  { id: 'mobile_postpaid', label: 'Mobile Postpaid' },
  { id: 'mobile_recharge', label: 'Mobile Recharge' },
  { id: 'rent', label: 'Rent' },
  { id: 'insurance', label: 'Insurance Premium' },
  { id: 'loan_emi', label: 'Loan / EMI' },
  { id: 'credit_card', label: 'Credit Card Bill Reminder' },
  { id: 'maintenance', label: 'Society / Maintenance' },
  { id: 'other', label: 'Other Payment' },
];

export const PAYMENT_METHODS: { id: PaymentMethod; label: string }[] = [
  { id: 'upi', label: 'UPI (Recorded)' },
  { id: 'debit_card', label: 'Debit Card (Recorded)' },
  { id: 'credit_card', label: 'Credit Card (Recorded)' },
  { id: 'net_banking', label: 'Net Banking (Recorded)' },
  { id: 'bank_transfer', label: 'Bank Transfer / NEFT / IMPS' },
  { id: 'auto_debit', label: 'Auto-Debit / NACH' },
  { id: 'cash', label: 'Cash' },
  { id: 'other', label: 'Other' },
];

interface BillFormModalProps {
  isOpen: boolean;
  editingBill: Bill | null;
  accounts: FinancialAccount[];
  categories: FinancialCategory[];
  onClose: () => void;
  onSaved: (bill: Bill) => void;
}

export const BillFormModal: React.FC<BillFormModalProps> = ({
  isOpen,
  editingBill,
  accounts,
  categories,
  onClose,
  onSaved,
}) => {
  const [billName, setBillName] = useState('');
  const [billCategory, setBillCategory] = useState<BillCategory>('electricity');
  const [providerName, setProviderName] = useState('');
  const [accountRef, setAccountRef] = useState('');
  const [description, setDescription] = useState('');
  const [billType, setBillType] = useState<BillType>('recurring');
  const [frequency, setFrequency] = useState<BillFrequency>('monthly');
  const [customDays, setCustomDays] = useState('30');
  const [isVariable, setIsVariable] = useState(false);
  const [expectedAmount, setExpectedAmount] = useState('');
  const [currentAmount, setCurrentAmount] = useState('');
  const [dueDate, setDueDate] = useState(new Date().toISOString().split('T')[0]);
  const [endDate, setEndDate] = useState('');
  const [preferredMethod, setPreferredMethod] = useState<PaymentMethod>('upi');
  const [linkedAccountId, setLinkedAccountId] = useState('');
  const [financialCategoryId, setFinancialCategoryId] = useState('');
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [reminderOffsets, setReminderOffsets] = useState<number[]>([7, 3, 1, 0]);
  const [inAppChannel, setInAppChannel] = useState(true);
  const [emailChannel, setEmailChannel] = useState(false);
  const [smsChannel, setSmsChannel] = useState(false);
  const [docFile, setDocFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    setDocFile(null);
    if (editingBill) {
      setBillName(editingBill.bill_name);
      setBillCategory(editingBill.bill_category);
      setProviderName(editingBill.provider_name || '');
      setAccountRef(editingBill.account_reference || '');
      setDescription(editingBill.description || '');
      setBillType(editingBill.bill_type);
      setFrequency(editingBill.frequency || 'monthly');
      setIsVariable(editingBill.is_variable_amount);
      setExpectedAmount(editingBill.expected_amount ? String(editingBill.expected_amount) : '');
      setCurrentAmount(editingBill.current_amount ? String(editingBill.current_amount) : '');
      setDueDate(editingBill.due_date);
      setEndDate('');
      setPreferredMethod((editingBill.preferred_payment_method as PaymentMethod) || 'upi');
      setLinkedAccountId(editingBill.linked_account_id || '');
      setFinancialCategoryId(editingBill.financial_category_id || '');
      setReminderEnabled(editingBill.reminder_enabled);
      setReminderOffsets(editingBill.reminder_days_before || [7, 3, 1, 0]);
      setInAppChannel(editingBill.notification_channels?.in_app ?? true);
      setEmailChannel(Boolean(editingBill.notification_channels?.email));
      setSmsChannel(Boolean(editingBill.notification_channels?.sms));
    } else {
      setBillName('');
      setBillCategory('electricity');
      setProviderName('');
      setAccountRef('');
      setDescription('');
      setBillType('recurring');
      setFrequency('monthly');
      setCustomDays('30');
      setIsVariable(false);
      setExpectedAmount('');
      setCurrentAmount('');
      setDueDate(new Date().toISOString().split('T')[0]);
      setEndDate('');
      setPreferredMethod('upi');
      setLinkedAccountId('');
      setFinancialCategoryId('');
      setReminderEnabled(true);
      setReminderOffsets([7, 3, 1, 0]);
      setInAppChannel(true);
      setEmailChannel(false);
      setSmsChannel(false);
    }
  }, [isOpen, editingBill]);

  if (!isOpen) return null;

  const toggleOffset = (d: number) => {
    setReminderOffsets((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort((a, b) => b - a)
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    if (!billName.trim()) {
      setError('Bill name is required.');
      return;
    }
    if (!isVariable && !expectedAmount && !currentAmount) {
      setError('Fixed-amount bills require an expected or current bill amount.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      let saved: Bill;
      if (editingBill) {
        saved = await billsApi.updateBill(editingBill.id, {
          bill_name: billName.trim(),
          bill_category: billCategory,
          provider_name: providerName.trim() || null,
          account_reference: accountRef.trim() || null,
          description: description.trim() || null,
          is_variable_amount: isVariable,
          expected_amount: expectedAmount ? expectedAmount : null,
          current_amount: currentAmount ? currentAmount : null,
          due_date: dueDate,
          preferred_payment_method: preferredMethod,
          linked_account_id: linkedAccountId || null,
          financial_category_id: financialCategoryId || null,
          reminder_enabled: reminderEnabled,
          reminder_days_before: reminderOffsets.length > 0 ? reminderOffsets : [0],
          notification_channels: {
            in_app: inAppChannel,
            email: emailChannel,
            sms: smsChannel,
          },
        });
      } else {
        saved = await billsApi.createBill({
          bill_name: billName.trim(),
          bill_category: billCategory,
          provider_name: providerName.trim() || null,
          account_reference: accountRef.trim() || null,
          description: description.trim() || null,
          bill_type: billType,
          frequency: billType === 'recurring' ? frequency : null,
          custom_interval_days:
            billType === 'recurring' && frequency === 'custom' ? Number(customDays || 30) : null,
          is_variable_amount: isVariable,
          expected_amount: expectedAmount ? expectedAmount : null,
          current_amount: currentAmount ? currentAmount : null,
          currency: 'INR',
          due_date: dueDate,
          end_date: billType === 'recurring' && endDate ? endDate : null,
          preferred_payment_method: preferredMethod,
          linked_account_id: linkedAccountId || null,
          financial_category_id: financialCategoryId || null,
          reminder_enabled: reminderEnabled,
          reminder_days_before: reminderOffsets.length > 0 ? reminderOffsets : [7, 3, 1, 0],
          notification_channels: {
            in_app: inAppChannel,
            email: emailChannel,
            sms: smsChannel,
          },
        });
      }

      if (docFile) {
        await billsApi.uploadDocument(saved.id, docFile);
        saved = await billsApi.getBill(saved.id);
      }

      onSaved(saved);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save bill.');
    } finally {
      setSubmitting(false);
    }
  };

  const expenseCategories = categories.filter((c) => c.category_type === 'expense');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl relative my-8">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>

        <h3 className="text-lg font-bold text-gray-900">
          {editingBill ? `Edit Bill — ${editingBill.bill_name}` : 'Create Bill Obligation'}
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Track upcoming bills, recurring schedules, variable amounts, and due-date reminders.
        </p>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 mt-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Bill Name *</label>
              <input
                type="text"
                required
                placeholder="e.g., BESCOM Electricity, Airtel Fiber"
                value={billName}
                onChange={(e) => setBillName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Bill Category *</label>
              <select
                aria-label="Bill Category"
                value={billCategory}
                onChange={(e) => setBillCategory(e.target.value as BillCategory)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm"
              >
                {BILL_CATEGORIES.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Provider / Biller</label>
              <input
                type="text"
                placeholder="e.g., BESCOM, Jio, HDFC Card"
                value={providerName}
                onChange={(e) => setProviderName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Consumer / Ref No.</label>
              <input
                type="text"
                placeholder="e.g., CA-99881122"
                value={accountRef}
                onChange={(e) => setAccountRef(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          {!editingBill && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Bill Type *</label>
                  <select
                    aria-label="Bill Type"
                    value={billType}
                    onChange={(e) => setBillType(e.target.value as BillType)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
                  >
                    <option value="recurring">Recurring Bill</option>
                    <option value="one_time">One-Time Bill</option>
                  </select>
                </div>

                {billType === 'recurring' && (
                  <>
                    <div>
                      <label className="block font-semibold text-gray-700 mb-1">Frequency *</label>
                      <select
                        aria-label="Recurrence Frequency"
                        value={frequency}
                        onChange={(e) => setFrequency(e.target.value as BillFrequency)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
                      >
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                        <option value="quarterly">Quarterly</option>
                        <option value="half_yearly">Half-Yearly</option>
                        <option value="yearly">Yearly</option>
                        <option value="custom">Custom Days</option>
                      </select>
                    </div>
                    {frequency === 'custom' ? (
                      <div>
                        <label className="block font-semibold text-gray-700 mb-1">
                          Interval (Days)
                        </label>
                        <input
                          type="number"
                          min="1"
                          value={customDays}
                          onChange={(e) => setCustomDays(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        />
                      </div>
                    ) : (
                      <div>
                        <label className="block font-semibold text-gray-700 mb-1">
                          Optional End Date
                        </label>
                        <input
                          type="date"
                          value={endDate}
                          onChange={(e) => setEndDate(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Fixed vs Variable Amount + Due Date */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
            <div>
              <label className="flex items-center space-x-2 mb-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isVariable}
                  onChange={(e) => setIsVariable(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600"
                />
                <span className="font-semibold text-gray-800">Variable Bill Amount</span>
              </label>
              <label className="block font-semibold text-gray-700 mb-1">
                {isVariable ? 'Current Bill Amount (Optional ₹)' : 'Bill Amount (₹) *'}
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                placeholder={isVariable ? 'Leave blank if unknown yet' : '0.00'}
                value={currentAmount}
                onChange={(e) => {
                  setCurrentAmount(e.target.value);
                  if (!isVariable && !expectedAmount) {
                    setExpectedAmount(e.target.value);
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                {isVariable ? 'Estimated Typical Amount (₹)' : 'Expected Recurring Amount (₹)'}
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                placeholder="Optional estimate"
                value={expectedAmount}
                onChange={(e) => setExpectedAmount(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Due Date *</label>
              <input
                type="date"
                required
                aria-label="Due Date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Linked Account (Optional)
              </label>
              <select
                value={linkedAccountId}
                onChange={(e) => setLinkedAccountId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="">Select when recording payment</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Ledger Category</label>
              <select
                value={financialCategoryId}
                onChange={(e) => setFinancialCategoryId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="">Auto-map from bill category</option>
                {expenseCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Preferred Payment Label
              </label>
              <select
                value={preferredMethod}
                onChange={(e) => setPreferredMethod(e.target.value as PaymentMethod)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                {PAYMENT_METHODS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Reminder Settings */}
          <div className="p-3 bg-indigo-50/50 border border-indigo-200 rounded-xl space-y-2">
            <label className="flex items-center space-x-2 cursor-pointer font-semibold text-gray-800">
              <input
                type="checkbox"
                checked={reminderEnabled}
                onChange={(e) => setReminderEnabled(e.target.checked)}
                className="rounded border-gray-300 text-indigo-600"
              />
              <span>Enable Scheduled Due-Date Reminders</span>
            </label>

            {reminderEnabled && (
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-gray-600 font-medium">Remind me:</span>
                  {[
                    { d: 7, l: '7d before' },
                    { d: 3, l: '3d before' },
                    { d: 1, l: '1d before' },
                    { d: 0, l: 'Due date' },
                  ].map((item) => (
                    <button
                      key={item.d}
                      type="button"
                      onClick={() => toggleOffset(item.d)}
                      className={`px-2 py-1 rounded text-[11px] font-medium border ${
                        reminderOffsets.includes(item.d)
                          ? 'bg-indigo-600 text-white border-indigo-600'
                          : 'bg-white text-gray-600 border-gray-300'
                      }`}
                    >
                      {item.l}
                    </button>
                  ))}
                </div>

                <div className="flex items-center space-x-3">
                  <label className="inline-flex items-center space-x-1">
                    <input
                      type="checkbox"
                      checked={inAppChannel}
                      onChange={(e) => setInAppChannel(e.target.checked)}
                    />
                    <span>In-App</span>
                  </label>
                  <label className="inline-flex items-center space-x-1">
                    <input
                      type="checkbox"
                      checked={emailChannel}
                      onChange={(e) => setEmailChannel(e.target.checked)}
                    />
                    <span>Email</span>
                  </label>
                  <label className="inline-flex items-center space-x-1">
                    <input
                      type="checkbox"
                      checked={smsChannel}
                      onChange={(e) => setSmsChannel(e.target.checked)}
                    />
                    <span>SMS</span>
                  </label>
                </div>
              </div>
            )}
          </div>

          {!editingBill && (
            <div>
              <label className="block font-semibold text-gray-700 mb-1">
                Supporting Bill Document (Optional — PDF, PNG, JPG, CSV, XLSX up to 10 MB)
              </label>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.csv,.xlsx"
                onChange={(e) => setDocFile(e.target.files?.[0] || null)}
                className="w-full text-xs text-gray-600"
              />
            </div>
          )}

          <div className="flex justify-end space-x-2 pt-3 border-t border-gray-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-semibold inline-flex items-center space-x-1.5"
            >
              {submitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
              <span>{editingBill ? 'Save Changes' : 'Create Bill'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface RecordPaymentModalProps {
  bill: Bill | null;
  accounts: FinancialAccount[];
  onClose: () => void;
  onRecorded: (updated: Bill) => void;
}

export const RecordPaymentModal: React.FC<RecordPaymentModalProps> = ({
  bill,
  accounts,
  onClose,
  onRecorded,
}) => {
  const [amount, setAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [accountId, setAccountId] = useState('');
  const [method, setMethod] = useState<PaymentMethod>('upi');
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [markPaid, setMarkPaid] = useState(true);
  const [step, setStep] = useState<'form' | 'confirm'>('form');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idemKey, setIdemKey] = useState('');

  useEffect(() => {
    if (!bill) return;
    setStep('form');
    setError(null);
    setIdemKey(`pay-${bill.id}-${Date.now()}`);
    const defaultAmt =
      bill.remaining_due ?? bill.current_amount ?? bill.expected_amount ?? '';
    setAmount(defaultAmt ? String(defaultAmt) : '');
    setPaymentDate(new Date().toISOString().split('T')[0]);
    const defaultAcc =
      accounts.find((a) => a.account_type !== 'credit_card')?.id || accounts[0]?.id || '';
    setAccountId(
      bill.linked_account_id && bill.bill_category !== 'credit_card'
        ? bill.linked_account_id
        : defaultAcc
    );
    setMethod((bill.preferred_payment_method as PaymentMethod) || 'upi');
    setReference('');
    setNotes('');
    setMarkPaid(true);
  }, [bill, accounts]);

  if (!bill) return null;

  const selectedAccount = accounts.find((a) => a.id === accountId);

  const handleContinue = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const num = parseFloat(amount);
    if (!amount || isNaN(num) || num <= 0) {
      setError('Enter a valid positive payment amount.');
      return;
    }
    if (!accountId) {
      setError('Select the financial account used to make this payment.');
      return;
    }
    setStep('confirm');
  };

  const handleConfirmRecord = async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await billsApi.recordPayment(bill.id, {
        amount_paid: Number(amount).toFixed(2),
        payment_date: paymentDate,
        financial_account_id: accountId,
        payment_method: method,
        reference_number: reference.trim() || undefined,
        notes: notes.trim() || undefined,
        idempotency_key: idemKey,
        mark_as_fully_paid: markPaid,
      });
      onRecorded(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to record payment.');
      setStep('form');
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

        <h3 className="text-lg font-bold text-gray-900">Record Bill Payment</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Bill: <strong>{bill.bill_name}</strong> (Due {formatDate(bill.due_date)})
        </p>

        <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-900 flex items-start space-x-2">
          <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <span>
            <strong>Manual Payment Recording Only:</strong> This records a payment you have already
            completed externally and posts it to your financial ledger. The app does{' '}
            <strong>not</strong> execute live UPI, card, or net-banking debits.
          </span>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
            {error}
          </div>
        )}

        {step === 'form' ? (
          <form onSubmit={handleContinue} className="space-y-3.5 mt-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Amount Paid (₹) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  aria-label="Amount Paid"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm"
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Payment Date *</label>
                <input
                  type="date"
                  required
                  aria-label="Payment Date"
                  value={paymentDate}
                  onChange={(e) => setPaymentDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Financial Account Used *</label>
              <select
                required
                aria-label="Financial Account Used"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                <option value="">Select account...</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({formatINR(a.current_balance)})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Payment Method</label>
                <select
                  aria-label="Payment Method"
                  value={method}
                  onChange={(e) => setMethod(e.target.value as PaymentMethod)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
                >
                  {PAYMENT_METHODS.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Reference / UTR No.</label>
                <input
                  type="text"
                  placeholder="Optional reference"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Notes</label>
              <input
                type="text"
                placeholder="Optional note"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>

            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="checkbox"
                checked={markPaid}
                onChange={(e) => setMarkPaid(e.target.checked)}
                className="rounded border-gray-300 text-emerald-600"
              />
              <span className="text-gray-700 font-medium">
                Mark bill as fully settled (also advances recurring schedule)
              </span>
            </label>

            <div className="flex justify-end space-x-2 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium text-gray-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold"
              >
                Review Payment Confirmation
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4 mt-4">
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-500">Bill:</span>
                <span className="font-semibold text-gray-900">{bill.bill_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Amount Recorded:</span>
                <span className="font-bold text-emerald-700">{formatINR(amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Account Debited:</span>
                <span className="font-semibold text-gray-900">
                  {selectedAccount?.name || 'Selected Account'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Date &amp; Method:</span>
                <span className="font-medium text-gray-800">
                  {formatDate(paymentDate)} • {method.toUpperCase()}
                </span>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                disabled={submitting}
                onClick={() => setStep('form')}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium text-gray-700"
              >
                Back &amp; Edit
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleConfirmRecord}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg font-semibold inline-flex items-center space-x-1.5"
              >
                {submitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <CheckCircle2 className="w-4 h-4" />
                <span>Confirm &amp; Record Payment</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

interface BillDetailsModalProps {
  bill: Bill | null;
  onClose: () => void;
  onEdit: (bill: Bill) => void;
  onRecordPayment: (bill: Bill) => void;
  onUpdated: (bill: Bill) => void;
  onArchive: (bill: Bill) => void;
}

export const BillDetailsModal: React.FC<BillDetailsModalProps> = ({
  bill,
  onClose,
  onEdit,
  onRecordPayment,
  onUpdated,
  onArchive,
}) => {
  const [recentTxs, setRecentTxs] = useState<FinancialTransaction[]>([]);
  const [selectedTxId, setSelectedTxId] = useState('');
  const [linking, setLinking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    if (!bill || bill.derived_status === 'paid' || bill.derived_status === 'archived') return;
    financeApi
      .listTransactions({ transaction_type: 'expense', page: 1, page_size: 20 })
      .then((res) => setRecentTxs(res.items))
      .catch(() => {});
  }, [bill?.id]);

  if (!bill) return null;

  const handleLinkTx = async () => {
    if (!selectedTxId || linking) return;
    setLinking(true);
    setDetailError(null);
    try {
      const updated = await billsApi.linkTransaction(bill.id, {
        transaction_id: selectedTxId,
        payment_method: (bill.preferred_payment_method as PaymentMethod) || 'upi',
        mark_as_fully_paid: true,
      });
      setSelectedTxId('');
      onUpdated(updated);
    } catch (err: unknown) {
      setDetailError(err instanceof Error ? err.message : 'Failed to link transaction.');
    } finally {
      setLinking(false);
    }
  };

  const handleDocUpload = async (file: File | null) => {
    if (!file || uploading) return;
    setUploading(true);
    setDetailError(null);
    try {
      await billsApi.uploadDocument(bill.id, file);
      const fresh = await billsApi.getBill(bill.id);
      onUpdated(fresh);
    } catch (err: unknown) {
      setDetailError(err instanceof Error ? err.message : 'Document upload failed.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-3xl w-full p-6 shadow-xl relative my-8 space-y-5 text-xs">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 pr-8">
          <div>
            <h3 className="text-xl font-bold text-gray-900">{bill.bill_name}</h3>
            <p className="text-gray-500 mt-0.5">
              {bill.provider_name || 'Biller'} • {bill.bill_category.replace('_', ' ').toUpperCase()}{' '}
              • {bill.bill_type === 'recurring' ? `Recurring (${bill.frequency})` : 'One-Time'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {bill.derived_status !== 'paid' && bill.derived_status !== 'archived' && (
              <button
                type="button"
                onClick={() => onRecordPayment(bill)}
                className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold"
              >
                Record Payment
              </button>
            )}
            {bill.derived_status !== 'archived' && (
              <>
                <button
                  type="button"
                  onClick={() => onEdit(bill)}
                  className="px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg font-medium"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => onArchive(bill)}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 hover:text-rose-700 rounded-lg font-medium inline-flex items-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Archive</span>
                </button>
              </>
            )}
          </div>
        </div>

        {detailError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {detailError}
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div className="text-gray-500">Due Date</div>
            <div className="font-bold text-gray-900 text-sm mt-0.5">{formatDate(bill.due_date)}</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div className="text-gray-500">Amount / Remaining</div>
            <div className="font-bold text-gray-900 text-sm mt-0.5">
              {bill.is_amount_unknown
                ? 'Variable (Unknown)'
                : formatINR(bill.remaining_due ?? bill.current_amount ?? bill.expected_amount)}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div className="text-gray-500">Total Paid</div>
            <div className="font-bold text-emerald-700 text-sm mt-0.5">
              {formatINR(bill.amount_paid_total)}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div className="text-gray-500">Derived Status</div>
            <div className="font-bold uppercase text-sm mt-0.5">{bill.derived_status.replace('_', ' ')}</div>
          </div>
        </div>

        {/* Link existing transaction */}
        {bill.derived_status !== 'paid' && bill.derived_status !== 'archived' && recentTxs.length > 0 && (
          <div className="p-3.5 bg-blue-50/50 border border-blue-200 rounded-xl space-y-2">
            <div className="font-semibold text-gray-800 flex items-center space-x-1.5">
              <Link2 className="w-3.5 h-3.5 text-blue-600" />
              <span>Already recorded in Transactions or CSV Import? Link without duplicating expense:</span>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <select
                value={selectedTxId}
                onChange={(e) => setSelectedTxId(e.target.value)}
                className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
              >
                <option value="">Select existing transaction...</option>
                {recentTxs.map((tx) => (
                  <option key={tx.id} value={tx.id}>
                    {formatDate(tx.transaction_date)} — {tx.description} ({formatINR(tx.amount)})
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={!selectedTxId || linking}
                onClick={handleLinkTx}
                className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium"
              >
                Link Transaction
              </button>
            </div>
          </div>
        )}

        {/* Payment History */}
        <div>
          <h4 className="font-bold text-gray-800 mb-2">
            Payment History ({bill.payments.length})
          </h4>
          {bill.payments.length === 0 ? (
            <p className="text-gray-500 p-3 bg-gray-50 rounded-lg">No payments recorded yet.</p>
          ) : (
            <div className="border border-gray-200 rounded-xl overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-gray-50 border-b border-gray-200 text-gray-600">
                  <tr>
                    <th className="py-2 px-3">Date</th>
                    <th className="py-2 px-3">Account</th>
                    <th className="py-2 px-3">Method</th>
                    <th className="py-2 px-3">Ref</th>
                    <th className="py-2 px-3">Ledger Tx</th>
                    <th className="py-2 px-3 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {bill.payments.map((p) => (
                    <tr key={p.id}>
                      <td className="py-2 px-3">{formatDate(p.payment_date)}</td>
                      <td className="py-2 px-3">{p.account_name || 'Linked Account'}</td>
                      <td className="py-2 px-3 uppercase">{p.payment_method}</td>
                      <td className="py-2 px-3 font-mono">{p.reference_number || '—'}</td>
                      <td className="py-2 px-3 font-mono text-gray-500">
                        {p.transaction_id ? p.transaction_id.slice(0, 8) : '—'}
                      </td>
                      <td className="py-2 px-3 text-right font-bold text-emerald-700">
                        {formatINR(p.amount_paid)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Scheduled Reminders */}
        <div>
          <h4 className="font-bold text-gray-800 mb-2">
            Reminder Schedule ({bill.reminders.length})
          </h4>
          {bill.reminders.length === 0 ? (
            <p className="text-gray-500 p-3 bg-gray-50 rounded-lg">No reminders configured.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {bill.reminders.map((r) => (
                <div
                  key={r.id}
                  className="p-2.5 border border-gray-200 rounded-lg flex items-center justify-between"
                >
                  <div>
                    <div className="font-semibold text-gray-800">
                      {r.offset_days === 0 ? 'On due date' : `${r.offset_days} day(s) before`}
                    </div>
                    <div className="text-[11px] text-gray-500">
                      Channels: {r.channels.join(', ')} • {formatDate(r.reminder_at)}
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                      r.delivery_status === 'delivered'
                        ? 'bg-emerald-50 text-emerald-700'
                        : r.delivery_status === 'cancelled'
                          ? 'bg-gray-100 text-gray-500'
                          : r.delivery_status === 'unavailable' || r.delivery_status === 'partial'
                            ? 'bg-amber-50 text-amber-700'
                            : 'bg-blue-50 text-blue-700'
                    }`}
                  >
                    {r.delivery_status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Supporting Documents */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-bold text-gray-800 flex items-center space-x-1.5">
              <Paperclip className="w-3.5 h-3.5" />
              <span>Supporting Documents ({bill.documents.length})</span>
            </h4>
            <label className="cursor-pointer px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium inline-flex items-center space-x-1">
              <Upload className="w-3 h-3" />
              <span>{uploading ? 'Uploading...' : 'Attach File'}</span>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.csv,.xlsx"
                className="hidden"
                onChange={(e) => handleDocUpload(e.target.files?.[0] || null)}
              />
            </label>
          </div>
          {bill.documents.length === 0 ? (
            <p className="text-gray-500 p-3 bg-gray-50 rounded-lg inline-flex items-center space-x-1.5 w-full">
              <Info className="w-3.5 h-3.5" />
              <span>No documents attached. Stored privately on server when uploaded.</span>
            </p>
          ) : (
            <div className="space-y-1.5">
              {bill.documents.map((d) => (
                <div
                  key={d.id}
                  className="p-2.5 border border-gray-200 rounded-lg flex items-center justify-between"
                >
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-blue-600" />
                    <span className="font-medium text-gray-900">{d.original_filename}</span>
                    <span className="text-[11px] text-gray-400">
                      ({(d.file_size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => billsApi.downloadDocument(bill.id, d.id, d.original_filename)}
                    className="px-2.5 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded font-medium inline-flex items-center space-x-1"
                  >
                    <Download className="w-3 h-3" />
                    <span>Download</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
