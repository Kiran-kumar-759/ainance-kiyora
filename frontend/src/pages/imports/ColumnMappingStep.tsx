import React, { useState, useEffect } from 'react';
import {
  ArrowRight,
  ArrowLeft,
  AlertCircle,
  RefreshCw,
  Table,
  BookmarkCheck,
} from 'lucide-react';
import { importsApi } from '../../services/importsApi';
import { ImportBatch, ImportColumns, ImportMappingConfig } from '../../types/imports';

interface ColumnMappingStepProps {
  batch: ImportBatch;
  onBack: () => void;
  onValidated: (updatedBatch: ImportBatch) => void;
}

export const ColumnMappingStep: React.FC<ColumnMappingStepProps> = ({
  batch,
  onBack,
  onValidated,
}) => {
  const [columnsData, setColumnsData] = useState<ImportColumns | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedSheet, setSelectedSheet] = useState<string>(batch.sheet_name || '');
  const [headerRowIndex, setHeaderRowIndex] = useState<number>(batch.header_row_index || 0);
  const [saveProfileName, setSaveProfileName] = useState<string>('');

  const [mapping, setMapping] = useState<ImportMappingConfig>({
    date_column: '',
    description_column: '',
    amount_mode: 'single',
    amount_column: '',
    debit_column: '',
    credit_column: '',
    type_column: '',
    sign_convention: 'negative_is_expense',
    reference_column: '',
    balance_column: '',
    merchant_column: '',
    notes_column: '',
    currency_column: '',
    date_format: 'auto',
    default_currency: 'INR',
  });

  const loadColumns = async (sheet?: string, hdrIdx?: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await importsApi.getColumns(batch.id, {
        sheet_name: sheet,
        header_row_index: hdrIdx,
      });
      setColumnsData(data);
      setSelectedSheet(data.selected_sheet);
      setHeaderRowIndex(data.header_row_index);

      const initial = (data.current_mapping || data.suggested_mapping || {}) as Partial<ImportMappingConfig>;
      setMapping((prev) => ({
        ...prev,
        date_column: initial.date_column || '',
        description_column: initial.description_column || '',
        amount_mode: initial.amount_mode || 'single',
        amount_column: initial.amount_column || '',
        debit_column: initial.debit_column || '',
        credit_column: initial.credit_column || '',
        type_column: initial.type_column || '',
        sign_convention: initial.sign_convention || 'negative_is_expense',
        reference_column: initial.reference_column || '',
        balance_column: initial.balance_column || '',
        merchant_column: initial.merchant_column || '',
        notes_column: initial.notes_column || '',
        currency_column: initial.currency_column || '',
        date_format: initial.date_format || 'auto',
        default_currency: initial.default_currency || 'INR',
      }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to inspect statement columns.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadColumns();
  }, [batch.id]);

  const handleApplyProfile = (profileId: string) => {
    const profile = columnsData?.saved_profiles.find((p) => p.id === profileId);
    if (!profile) return;
    const cfg = profile.mapping_configuration;
    setMapping((prev) => ({
      ...prev,
      ...cfg,
      date_column: cfg.date_column || '',
      description_column: cfg.description_column || '',
    }));
  };

  const isMappingValid = (): boolean => {
    if (!mapping.date_column || !mapping.description_column) return false;
    if (mapping.amount_mode === 'single') {
      return Boolean(mapping.amount_column);
    }
    return Boolean(mapping.debit_column || mapping.credit_column);
  };

  const handleConfirmMapping = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || !isMappingValid()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const payload: ImportMappingConfig = {
        ...mapping,
        amount_column: mapping.amount_mode === 'single' ? mapping.amount_column || null : null,
        debit_column: mapping.amount_mode === 'split' ? mapping.debit_column || null : null,
        credit_column: mapping.amount_mode === 'split' ? mapping.credit_column || null : null,
        type_column: mapping.type_column || null,
        reference_column: mapping.reference_column || null,
        balance_column: mapping.balance_column || null,
        merchant_column: mapping.merchant_column || null,
        notes_column: mapping.notes_column || null,
        currency_column: mapping.currency_column || null,
        sheet_name: selectedSheet || null,
        header_row_index: headerRowIndex,
        save_profile_name: saveProfileName.trim() || null,
      };
      const updated = await importsApi.saveMapping(batch.id, payload);
      onValidated(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to validate statement mapping.';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const columns = columnsData?.columns || [];
  const sampleRows = columnsData?.sample_mapped_rows || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <button
            type="button"
            onClick={onBack}
            className="text-xs text-gray-500 hover:text-gray-800 inline-flex items-center space-x-1 mb-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Imports</span>
          </button>
          <h2 className="text-xl font-bold text-gray-900">
            Map Statement Columns — {batch.original_filename}
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Target Account: <strong>{batch.account_name || 'Selected Account'}</strong> •{' '}
            {batch.file_type.toUpperCase()} • {batch.total_rows} detected rows
          </p>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start space-x-2">
          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {isLoading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-10 text-center text-gray-500 text-sm">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
          Inspecting file headers and sample rows...
        </div>
      ) : (
        <form onSubmit={handleConfirmMapping} className="space-y-6">
          {/* Parsing Options Bar (Sheet, Header Row, Saved Profiles) */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm grid grid-cols-1 md:grid-cols-3 gap-4">
            {columnsData && columnsData.available_sheets.length > 1 && (
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Excel Worksheet
                </label>
                <select
                  value={selectedSheet}
                  onChange={(e) => loadColumns(e.target.value, 0)}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white"
                >
                  {columnsData.available_sheets.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Header Row Position
              </label>
              <select
                value={headerRowIndex}
                onChange={(e) => loadColumns(selectedSheet, Number(e.target.value))}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white"
              >
                {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((idx) => (
                  <option key={idx} value={idx}>
                    Row {idx + 1}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Date Format Convention
              </label>
              <select
                value={mapping.date_format}
                onChange={(e) =>
                  setMapping({
                    ...mapping,
                    date_format: e.target.value as ImportMappingConfig['date_format'],
                  })
                }
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white"
              >
                <option value="auto">Auto-detect (Indian DD/MM/YYYY priority)</option>
                <option value="DD/MM/YYYY">DD/MM/YYYY (25/11/2026)</option>
                <option value="DD-MM-YYYY">DD-MM-YYYY (25-11-2026)</option>
                <option value="DD MMM YYYY">DD MMM YYYY (25 Nov 2026)</option>
                <option value="YYYY-MM-DD">YYYY-MM-DD (2026-11-25)</option>
                <option value="MM/DD/YYYY">MM/DD/YYYY (US format)</option>
              </select>
            </div>

            {columnsData && columnsData.saved_profiles.length > 0 && (
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Apply Saved Mapping Profile
                </label>
                <select
                  defaultValue=""
                  onChange={(e) => handleApplyProfile(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white"
                >
                  <option value="">-- Select saved profile --</option>
                  {columnsData.saved_profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.profile_name} ({p.file_format.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Required & Optional Field Mappings */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-5">
            <div className="border-b border-gray-100 pb-3">
              <h3 className="text-sm font-bold text-gray-900">Column Mapping Configuration</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Confirm how your statement columns correspond to normalized financial fields.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Transaction Date *
                </label>
                <select
                  required
                  value={mapping.date_column}
                  onChange={(e) => setMapping({ ...mapping, date_column: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                >
                  <option value="">Select column...</option>
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Description / Narration *
                </label>
                <select
                  required
                  value={mapping.description_column}
                  onChange={(e) => setMapping({ ...mapping, description_column: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                >
                  <option value="">Select column...</option>
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Amount Mode Toggle */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <span className="text-xs font-bold text-gray-800">Amount Column Layout *</span>
                <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1">
                  <button
                    type="button"
                    onClick={() => setMapping({ ...mapping, amount_mode: 'single' })}
                    className={`px-3 py-1 text-xs font-medium rounded-md ${
                      mapping.amount_mode === 'single'
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    Single Signed Amount Column
                  </button>
                  <button
                    type="button"
                    onClick={() => setMapping({ ...mapping, amount_mode: 'split' })}
                    className={`px-3 py-1 text-xs font-medium rounded-md ${
                      mapping.amount_mode === 'split'
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    Separate Debit &amp; Credit Columns
                  </button>
                </div>
              </div>

              {mapping.amount_mode === 'single' ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      Amount Column *
                    </label>
                    <select
                      required
                      value={mapping.amount_column || ''}
                      onChange={(e) => setMapping({ ...mapping, amount_column: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                    >
                      <option value="">Select column...</option>
                      {columns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      DR/CR Indicator Column (Optional)
                    </label>
                    <select
                      value={mapping.type_column || ''}
                      onChange={(e) => setMapping({ ...mapping, type_column: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                    >
                      <option value="">None (use +/- sign)</option>
                      {columns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      Sign Interpretation
                    </label>
                    <select
                      value={mapping.sign_convention}
                      onChange={(e) =>
                        setMapping({
                          ...mapping,
                          sign_convention: e.target.value as 'negative_is_expense' | 'positive_is_expense',
                        })
                      }
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                    >
                      <option value="negative_is_expense">
                        Negative (-₹) = Expense, Positive (+₹) = Income
                      </option>
                      <option value="positive_is_expense">
                        Positive (+₹) = Expense, Negative (-₹) = Income
                      </option>
                    </select>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      Debit / Withdrawal Column (Expense)
                    </label>
                    <select
                      value={mapping.debit_column || ''}
                      onChange={(e) => setMapping({ ...mapping, debit_column: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                    >
                      <option value="">Select column...</option>
                      {columns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      Credit / Deposit Column (Income)
                    </label>
                    <select
                      value={mapping.credit_column || ''}
                      onChange={(e) => setMapping({ ...mapping, credit_column: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                    >
                      <option value="">Select column...</option>
                      {columns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}
            </div>

            {/* Optional Metadata Columns */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Transaction Reference / UTR
                </label>
                <select
                  value={mapping.reference_column || ''}
                  onChange={(e) => setMapping({ ...mapping, reference_column: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white"
                >
                  <option value="">None</option>
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Running Balance (Info Only)
                </label>
                <select
                  value={mapping.balance_column || ''}
                  onChange={(e) => setMapping({ ...mapping, balance_column: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white"
                >
                  <option value="">None</option>
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Merchant / Payee
                </label>
                <select
                  value={mapping.merchant_column || ''}
                  onChange={(e) => setMapping({ ...mapping, merchant_column: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white"
                >
                  <option value="">None</option>
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Notes</label>
                <select
                  value={mapping.notes_column || ''}
                  onChange={(e) => setMapping({ ...mapping, notes_column: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white"
                >
                  <option value="">None</option>
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Save Profile Option */}
            <div className="pt-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-t border-gray-100">
              <div className="flex items-center space-x-2 flex-1 max-w-sm">
                <BookmarkCheck className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <input
                  type="text"
                  placeholder="Optional: Save mapping as profile (e.g. HDFC Savings)"
                  value={saveProfileName}
                  onChange={(e) => setSaveProfileName(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs border border-gray-300 rounded-lg"
                />
              </div>

              <button
                type="submit"
                disabled={!isMappingValid() || isSubmitting}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg shadow-sm inline-flex items-center space-x-2"
              >
                {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                <span>Validate &amp; Review Transactions</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Sample Rows Preview */}
          {sampleRows.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
              <div className="flex items-center space-x-2 mb-3">
                <Table className="w-4 h-4 text-gray-500" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Raw Statement Preview (First {sampleRows.length} Data Rows)
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 text-gray-600">
                      {columns.map((c) => (
                        <th key={c} className="py-2 px-3 font-semibold whitespace-nowrap">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sampleRows.map((row, idx) => (
                      <tr key={idx}>
                        {columns.map((c) => (
                          <td key={c} className="py-2 px-3 text-gray-700 whitespace-nowrap">
                            {String(row[c] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </form>
      )}
    </div>
  );
};
