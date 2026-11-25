import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Search,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Edit2,
  X,
  ChevronLeft,
  ChevronRight,
  Ban,
  CopyCheck,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import { importsApi } from '../../services/importsApi';
import { FinancialCategory } from '../../types/finance';
import { ImportBatch, ImportRow } from '../../types/imports';
import { formatDate, formatINR } from '../../lib/formatters';

interface TransactionReviewStepProps {
  batch: ImportBatch;
  onBackToList: () => void;
  onBackToMapping: () => void;
  onBatchUpdated: (batch: ImportBatch) => void;
  onProceedToConfirm: () => void;
}

export const TransactionReviewStep: React.FC<TransactionReviewStepProps> = ({
  batch,
  onBackToList,
  onBackToMapping,
  onBatchUpdated,
  onProceedToConfirm,
}) => {
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [categories, setCategories] = useState<FinancialCategory[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [search, setSearch] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('row_asc');

  // Edit modal
  const [editingRow, setEditingRow] = useState<ImportRow | null>(null);
  const [editDate, setEditDate] = useState<string>('');
  const [editDesc, setEditDesc] = useState<string>('');
  const [editMerchant, setEditMerchant] = useState<string>('');
  const [editAmount, setEditAmount] = useState<string>('');
  const [editType, setEditType] = useState<'income' | 'expense'>('expense');
  const [editCategoryId, setEditCategoryId] = useState<string>('');

  const loadCategories = async () => {
    try {
      const cats = await financeApi.listCategories();
      setCategories(cats);
    } catch {
      // Non-fatal
    }
  };

  const fetchRowsAndBatch = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [rowsRes, freshBatch] = await Promise.all([
        importsApi.listRows(batch.id, {
          status_filter: statusFilter || undefined,
          search: search.trim() || undefined,
          sort_by: sortBy,
          page,
          page_size: 20,
        }),
        importsApi.getImport(batch.id),
      ]);
      setRows(rowsRes.items);
      setTotal(rowsRes.total);
      setTotalPages(rowsRes.total_pages);
      onBatchUpdated(freshBatch);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load statement rows.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    fetchRowsAndBatch();
  }, [batch.id, page, statusFilter, sortBy]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchRowsAndBatch();
  };

  const handleBulkSelect = async (action: 'select_all_valid' | 'deselect_all') => {
    if (isMutating) return;
    setIsMutating(true);
    setError(null);
    try {
      const updated = await importsApi.bulkSelectRows(batch.id, action);
      onBatchUpdated(updated);
      await fetchRowsAndBatch();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Bulk update failed.');
    } finally {
      setIsMutating(false);
    }
  };

  const handleToggleSelect = async (row: ImportRow) => {
    if (isMutating) return;
    setIsMutating(true);
    setError(null);
    try {
      await importsApi.updateRow(batch.id, row.id, { is_selected: !row.is_selected });
      await fetchRowsAndBatch();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update selection.');
    } finally {
      setIsMutating(false);
    }
  };

  const handleInlineCategoryChange = async (row: ImportRow, categoryId: string) => {
    if (isMutating) return;
    setIsMutating(true);
    setError(null);
    try {
      await importsApi.updateRow(batch.id, row.id, {
        category_id: categoryId || null,
        clear_category: !categoryId,
      });
      await fetchRowsAndBatch();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update category.');
    } finally {
      setIsMutating(false);
    }
  };

  const handleToggleExclude = async (row: ImportRow) => {
    if (isMutating) return;
    setIsMutating(true);
    setError(null);
    try {
      const exclude = row.validation_status !== 'excluded';
      await importsApi.updateRow(batch.id, row.id, { exclude });
      await fetchRowsAndBatch();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update exclusion.');
    } finally {
      setIsMutating(false);
    }
  };

  const handleDuplicateDecision = async (row: ImportRow, decision: 'import' | 'skip') => {
    if (isMutating) return;
    setIsMutating(true);
    setError(null);
    try {
      await importsApi.reviewDuplicate(batch.id, row.id, decision);
      await fetchRowsAndBatch();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to resolve duplicate.');
    } finally {
      setIsMutating(false);
    }
  };

  const openEditRow = (row: ImportRow) => {
    setEditingRow(row);
    setEditDate(row.normalized_date || new Date().toISOString().split('T')[0]);
    setEditDesc(row.normalized_description || '');
    setEditMerchant(row.normalized_merchant || '');
    setEditAmount(row.normalized_amount ? String(row.normalized_amount) : '');
    setEditType(row.normalized_type || 'expense');
    setEditCategoryId(row.category_id || '');
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingRow || isMutating) return;
    setIsMutating(true);
    setError(null);
    try {
      await importsApi.updateRow(batch.id, editingRow.id, {
        normalized_date: editDate,
        normalized_description: editDesc.trim(),
        normalized_merchant: editMerchant.trim() || null,
        normalized_amount: editAmount,
        normalized_type: editType,
        category_id: editCategoryId || null,
        clear_category: !editCategoryId,
      });
      setEditingRow(null);
      await fetchRowsAndBatch();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save row changes.');
    } finally {
      setIsMutating(false);
    }
  };

  const renderStatusBadge = (row: ImportRow) => {
    const map: Record<string, { label: string; cls: string }> = {
      valid: { label: 'Valid', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
      invalid: { label: 'Invalid', cls: 'bg-rose-50 text-rose-700 border-rose-200' },
      needs_review: { label: 'Needs Review', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
      duplicate: { label: 'Duplicate', cls: 'bg-slate-100 text-slate-700 border-slate-300' },
      potential_duplicate: {
        label: 'Potential Duplicate',
        cls: 'bg-orange-50 text-orange-700 border-orange-200',
      },
      excluded: { label: 'Excluded', cls: 'bg-gray-100 text-gray-500 border-gray-200' },
      imported: { label: 'Imported', cls: 'bg-blue-50 text-blue-700 border-blue-200' },
    };
    const info = map[row.validation_status] || {
      label: row.validation_status,
      cls: 'bg-gray-100 text-gray-700 border-gray-200',
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${info.cls}`}>
        {info.label}
      </span>
    );
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <button
              type="button"
              onClick={onBackToList}
              className="text-xs text-gray-500 hover:text-gray-800 inline-flex items-center space-x-1"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>All Imports</span>
            </button>
            <span className="text-gray-300">|</span>
            <button
              type="button"
              onClick={onBackToMapping}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              Remap Columns
            </button>
          </div>
          <h2 className="text-xl font-bold text-gray-900">
            Review &amp; Validate — {batch.original_filename}
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Target Account: <strong>{batch.account_name}</strong> • Review validation flags,
            resolve potential duplicates, assign categories, and select rows to import.
          </p>
        </div>

        <button
          type="button"
          onClick={onProceedToConfirm}
          disabled={batch.valid_rows === 0}
          className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg shadow-sm inline-flex items-center space-x-2"
        >
          <span>Review Import Summary</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Validation Status Pills */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-2.5 text-xs">
        <div className="bg-white p-3 rounded-xl border border-gray-200">
          <div className="text-gray-500">Total Rows</div>
          <div className="text-lg font-bold text-gray-900">{batch.total_rows}</div>
        </div>
        <div className="bg-emerald-50/60 p-3 rounded-xl border border-emerald-200">
          <div className="text-emerald-700 font-medium">Valid</div>
          <div className="text-lg font-bold text-emerald-800">{batch.valid_rows}</div>
        </div>
        <div className="bg-orange-50/70 p-3 rounded-xl border border-orange-200">
          <div className="text-orange-700 font-medium">Potential Dup</div>
          <div className="text-lg font-bold text-orange-800">{batch.potential_duplicate_rows}</div>
        </div>
        <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
          <div className="text-slate-600 font-medium">Duplicates</div>
          <div className="text-lg font-bold text-slate-800">{batch.duplicate_rows}</div>
        </div>
        <div className="bg-amber-50/70 p-3 rounded-xl border border-amber-200">
          <div className="text-amber-700 font-medium">Needs Review</div>
          <div className="text-lg font-bold text-amber-800">{batch.needs_review_rows}</div>
        </div>
        <div className="bg-rose-50/70 p-3 rounded-xl border border-rose-200">
          <div className="text-rose-700 font-medium">Invalid</div>
          <div className="text-lg font-bold text-rose-800">{batch.invalid_rows}</div>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search, Filter & Bulk Selection Bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <form onSubmit={handleSearch} className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search description or ref..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs border border-gray-300 rounded-lg"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
          >
            <option value="">All Statuses</option>
            <option value="valid">Valid</option>
            <option value="potential_duplicate">Potential Duplicates</option>
            <option value="duplicate">Duplicates</option>
            <option value="needs_review">Needs Review</option>
            <option value="invalid">Invalid</option>
            <option value="excluded">Excluded</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
          >
            <option value="row_asc">Row Order</option>
            <option value="date_desc">Newest Date</option>
            <option value="date_asc">Oldest Date</option>
            <option value="amount_desc">Highest Amount</option>
            <option value="amount_asc">Lowest Amount</option>
          </select>
          <button
            type="submit"
            className="px-3 py-1.5 bg-gray-900 text-white text-xs font-medium rounded-lg"
          >
            Filter
          </button>
        </form>

        <div className="flex items-center space-x-2 text-xs">
          <button
            type="button"
            disabled={isMutating}
            onClick={() => handleBulkSelect('select_all_valid')}
            className="px-3 py-1.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg font-medium border border-emerald-200 inline-flex items-center space-x-1"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Select All Valid</span>
          </button>
          <button
            type="button"
            disabled={isMutating}
            onClick={() => handleBulkSelect('deselect_all')}
            className="px-3 py-1.5 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-lg font-medium"
          >
            Deselect All
          </button>
        </div>
      </div>

      {/* Review Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500 text-xs">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
            Loading rows...
          </div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-xs">
            No rows match the current filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 uppercase text-[10px] font-bold">
                <tr>
                  <th className="py-2.5 px-3">Use</th>
                  <th className="py-2.5 px-3">Row</th>
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3">Description &amp; Errors</th>
                  <th className="py-2.5 px-3">Ref</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((row) => {
                  const compatibleCats = categories.filter(
                    (c) => !row.normalized_type || c.category_type === row.normalized_type
                  );
                  return (
                    <tr
                      key={row.id}
                      className={`hover:bg-gray-50/70 ${
                        row.validation_status === 'excluded' || row.validation_status === 'duplicate'
                          ? 'opacity-65 bg-gray-50/40'
                          : ''
                      }`}
                    >
                      <td className="py-2.5 px-3">
                        <input
                          type="checkbox"
                          disabled={row.validation_status !== 'valid' || isMutating}
                          checked={row.is_selected}
                          onChange={() => handleToggleSelect(row)}
                          aria-label={`Select row ${row.source_row_number}`}
                          className="rounded border-gray-300 text-blue-600"
                        />
                      </td>
                      <td className="py-2.5 px-3 text-gray-500 font-mono">
                        #{row.source_row_number}
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap font-medium text-gray-800">
                        {row.normalized_date ? formatDate(row.normalized_date) : '—'}
                      </td>
                      <td className="py-2.5 px-3 max-w-xs">
                        <div className="font-semibold text-gray-900">
                          {row.normalized_description || <span className="text-rose-500 italic">Missing description</span>}
                        </div>
                        {row.normalized_merchant && (
                          <div className="text-[11px] text-gray-500">{row.normalized_merchant}</div>
                        )}
                        {row.validation_errors && row.validation_errors.length > 0 && (
                          <div className="mt-1 space-y-0.5">
                            {row.validation_errors.map((err, i) => (
                              <div key={i} className="text-[11px] text-amber-700 font-medium">
                                • {err}
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-[11px] font-mono text-gray-500">
                        {row.transaction_reference || '—'}
                      </td>
                      <td className="py-2.5 px-3">
                        {row.normalized_type ? (
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              row.normalized_type === 'income'
                                ? 'bg-emerald-50 text-emerald-700'
                                : 'bg-rose-50 text-rose-700'
                            }`}
                          >
                            {row.normalized_type}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold whitespace-nowrap">
                        {row.normalized_amount ? formatINR(row.normalized_amount) : '—'}
                      </td>
                      <td className="py-2.5 px-3">
                        <select
                          disabled={
                            row.validation_status === 'imported' ||
                            row.validation_status === 'invalid' ||
                            isMutating
                          }
                          value={row.category_id || ''}
                          onChange={(e) => handleInlineCategoryChange(row, e.target.value)}
                          className="px-2 py-1 text-[11px] border border-gray-300 rounded bg-white max-w-[140px]"
                        >
                          <option value="">Uncategorized</option>
                          {compatibleCats.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">{renderStatusBadge(row)}</td>
                      <td className="py-2.5 px-3 text-right whitespace-nowrap space-x-1">
                        {row.validation_status === 'potential_duplicate' && (
                          <>
                            <button
                              type="button"
                              disabled={isMutating}
                              onClick={() => handleDuplicateDecision(row, 'import')}
                              className="px-2 py-1 bg-emerald-600 text-white rounded text-[10px] font-semibold hover:bg-emerald-700 inline-flex items-center space-x-1"
                              title="Keep as legitimate transaction"
                            >
                              <CopyCheck className="w-3 h-3" />
                              <span>Keep</span>
                            </button>
                            <button
                              type="button"
                              disabled={isMutating}
                              onClick={() => handleDuplicateDecision(row, 'skip')}
                              className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-[10px] font-semibold hover:bg-gray-300"
                              title="Skip duplicate"
                            >
                              Skip
                            </button>
                          </>
                        )}
                        {row.validation_status !== 'imported' && (
                          <>
                            <button
                              type="button"
                              onClick={() => openEditRow(row)}
                              className="p-1 text-gray-500 hover:text-blue-600 rounded"
                              title="Edit Row"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              disabled={isMutating}
                              onClick={() => handleToggleExclude(row)}
                              className="p-1 text-gray-500 hover:text-amber-700 rounded"
                              title={
                                row.validation_status === 'excluded'
                                  ? 'Include Row'
                                  : 'Exclude Row'
                              }
                            >
                              <Ban className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-200 flex items-center justify-between text-xs text-gray-600">
            <span>
              Total {total} rows (Page {page} of {totalPages})
            </span>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2.5 py-1 bg-white border border-gray-200 rounded disabled:opacity-40 inline-flex items-center space-x-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Prev</span>
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-2.5 py-1 bg-white border border-gray-200 rounded disabled:opacity-40 inline-flex items-center space-x-1"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Edit Row Modal */}
      {editingRow && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl relative">
            <button
              type="button"
              onClick={() => setEditingRow(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-bold text-gray-900">
              Edit Statement Row #{editingRow.source_row_number}
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              Correct missing or ambiguous normalized fields before importing.
            </p>

            <form onSubmit={handleSaveEdit} className="space-y-3 mt-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Date *</label>
                  <input
                    type="date"
                    required
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Type *</label>
                  <select
                    value={editType}
                    onChange={(e) => {
                      setEditType(e.target.value as 'income' | 'expense');
                      setEditCategoryId('');
                    }}
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white"
                  >
                    <option value="expense">Expense (Debit)</option>
                    <option value="income">Income (Credit)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Description *
                </label>
                <input
                  type="text"
                  required
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
                />
              </div>

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
                    value={editAmount}
                    onChange={(e) => setEditAmount(e.target.value)}
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Category</label>
                  <select
                    value={editCategoryId}
                    onChange={(e) => setEditCategoryId(e.target.value)}
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white"
                  >
                    <option value="">Uncategorized</option>
                    {categories
                      .filter((c) => c.category_type === editType)
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Merchant / Payee
                </label>
                <input
                  type="text"
                  value={editMerchant}
                  onChange={(e) => setEditMerchant(e.target.value)}
                  className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
                />
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setEditingRow(null)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isMutating}
                  className="px-4 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg"
                >
                  Save &amp; Re-validate
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
