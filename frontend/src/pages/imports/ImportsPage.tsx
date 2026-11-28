import React, { useState, useEffect, useRef } from 'react';
import {
  FileSpreadsheet,
  Upload,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Trash2,
  Eye,
  Play,
  X,
  ArrowLeft,
  ShieldCheck,
  FileCheck2,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import { importsApi } from '../../services/importsApi';
import { FinancialAccount } from '../../types/finance';
import {
  ImportBatch,
  ImportCenterOverview,
  ImportCommitResponse,
  ImportRow,
  ImportSummary,
} from '../../types/imports';
import { formatDate, formatINR } from '../../lib/formatters';
import { ColumnMappingStep } from './ColumnMappingStep';
import { TransactionReviewStep } from './TransactionReviewStep';
import { WorkspaceStarterBanner } from '../../components/finance/WorkspaceStarterBanner';

interface ImportsPageProps {
  onNavigate: (view: string) => void;
}

type ActiveSubScreen =
  | 'center'
  | 'mapping'
  | 'review'
  | 'confirm'
  | 'results'
  | 'details';

export const ImportsPage: React.FC<ImportsPageProps> = ({ onNavigate }) => {
  const [overview, setOverview] = useState<ImportCenterOverview | null>(null);
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Navigation within Import Workflow
  const [subScreen, setSubScreen] = useState<ActiveSubScreen>('center');
  const [activeBatch, setActiveBatch] = useState<ImportBatch | null>(null);
  const [summaryData, setSummaryData] = useState<ImportSummary | null>(null);
  const [commitResult, setCommitResult] = useState<ImportCommitResponse | null>(null);
  const [detailsRows, setDetailsRows] = useState<ImportRow[]>([]);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Confirm commit state
  const [isCommitting, setIsCommitting] = useState<boolean>(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const loadCenterData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [ov, accs] = await Promise.all([
        importsApi.listImports(),
        financeApi.listAccounts(false),
      ]);
      setOverview(ov);
      setAccounts(accs);
      if (accs.length > 0 && !selectedAccountId) {
        setSelectedAccountId(accs[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load statement imports.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCenterData();
  }, []);

  const handleFilePicked = (file: File | null) => {
    setUploadError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const lower = file.name.toLowerCase();
    if (!lower.endsWith('.csv') && !lower.endsWith('.xlsx')) {
      setUploadError('Unsupported file type. Please choose a .csv or .xlsx bank statement.');
      setSelectedFile(null);
      return;
    }
    if (file.size === 0) {
      setUploadError('Selected file is empty (0 bytes).');
      setSelectedFile(null);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('File exceeds the 10 MB maximum upload limit.');
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isUploading) return;
    if (!selectedAccountId) {
      setUploadError('Please select a destination financial account.');
      return;
    }
    if (!selectedFile) {
      setUploadError('Please select or drop a .csv or .xlsx file.');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    try {
      const preview = await importsApi.uploadStatement(selectedAccountId, selectedFile, (pct) => {
        setUploadProgress(pct);
      });
      setIsUploadOpen(false);
      setSelectedFile(null);
      setActiveBatch(preview.batch);
      setSubScreen('mapping');
      await loadCenterData();
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Statement upload failed.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleOpenBatch = async (batch: ImportBatch) => {
    setError(null);
    setActiveBatch(batch);
    if (batch.status === 'mapping_required' || batch.status === 'uploaded') {
      setSubScreen('mapping');
    } else if (batch.status === 'ready_for_review') {
      setSubScreen('review');
    } else {
      await handleOpenDetails(batch);
    }
  };

  const handleOpenDetails = async (batch: ImportBatch) => {
    setError(null);
    setActiveBatch(batch);
    setSubScreen('details');
    try {
      const [fresh, rowsRes] = await Promise.all([
        importsApi.getImport(batch.id),
        importsApi.listRows(batch.id, { page: 1, page_size: 100 }),
      ]);
      setActiveBatch(fresh);
      setDetailsRows(rowsRes.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load import details.');
    }
  };

  const handleProceedToConfirm = async () => {
    if (!activeBatch) return;
    setConfirmError(null);
    try {
      const summary = await importsApi.getSummary(activeBatch.id);
      setSummaryData(summary);
      setSubScreen('confirm');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load import summary.');
    }
  };

  const handleExecuteCommit = async () => {
    if (!activeBatch || isCommitting) return;
    setIsCommitting(true);
    setConfirmError(null);
    try {
      const result = await importsApi.commitImport(activeBatch.id);
      setCommitResult(result);
      setActiveBatch(result.batch);
      setSubScreen('results');
      await loadCenterData();
    } catch (err: unknown) {
      setConfirmError(err instanceof Error ? err.message : 'Import execution failed.');
    } finally {
      setIsCommitting(false);
    }
  };

  const handleDeleteBatch = async (batch: ImportBatch) => {
    if (!confirm(`Cancel and delete import "${batch.original_filename}"?`)) return;
    setError(null);
    try {
      await importsApi.deleteImport(batch.id);
      await loadCenterData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete import batch.');
    }
  };

  const renderBatchStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      ready_for_review: 'bg-blue-50 text-blue-700 border-blue-200',
      mapping_required: 'bg-amber-50 text-amber-700 border-amber-200',
      failed: 'bg-rose-50 text-rose-700 border-rose-200',
      cancelled: 'bg-gray-100 text-gray-500 border-gray-200',
    };
    const cls = styles[status] || 'bg-gray-100 text-gray-700 border-gray-200';
    return (
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${cls}`}>
        {status.replace(/_/g, ' ')}
      </span>
    );
  };

  if (subScreen === 'mapping' && activeBatch) {
    return (
      <ColumnMappingStep
        batch={activeBatch}
        onBack={() => {
          setSubScreen('center');
          loadCenterData();
        }}
        onValidated={(updated) => {
          setActiveBatch(updated);
          setSubScreen('review');
        }}
      />
    );
  }

  if (subScreen === 'review' && activeBatch) {
    return (
      <TransactionReviewStep
        batch={activeBatch}
        onBackToList={() => {
          setSubScreen('center');
          loadCenterData();
        }}
        onBackToMapping={() => setSubScreen('mapping')}
        onBatchUpdated={(updated) => setActiveBatch(updated)}
        onProceedToConfirm={handleProceedToConfirm}
      />
    );
  }

  if (subScreen === 'confirm' && activeBatch && summaryData) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <button
          type="button"
          onClick={() => setSubScreen('review')}
          className="text-xs text-gray-500 hover:text-gray-800 inline-flex items-center space-x-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Transaction Review</span>
        </button>

        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-5">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Confirm Statement Import</h2>
            <p className="text-xs text-gray-500 mt-1">
              Selected transactions will be persisted through the double-entry financial ledger into{' '}
              <strong>{summaryData.account_name}</strong> and immediately reflected in your account
              balance.
            </p>
          </div>

          {confirmError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
              <span>{confirmError}</span>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
              <div className="text-gray-500">Total Parsed Rows</div>
              <div className="text-lg font-bold text-gray-900">{summaryData.total_rows}</div>
            </div>
            <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
              <div className="text-blue-700 font-medium">Selected to Import</div>
              <div className="text-lg font-bold text-blue-900">{summaryData.selected_rows}</div>
            </div>
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
              <div className="text-gray-500">Duplicates / Invalid / Skipped</div>
              <div className="text-lg font-bold text-gray-700">
                {summaryData.duplicate_rows +
                  summaryData.invalid_rows +
                  summaryData.excluded_rows +
                  summaryData.potential_duplicate_rows}
              </div>
            </div>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Total Income Selected:</span>
              <span className="font-bold text-emerald-700">
                +{formatINR(summaryData.selected_income)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Total Expenses Selected:</span>
              <span className="font-bold text-rose-700">
                -{formatINR(summaryData.selected_expenses)}
              </span>
            </div>
            <div className="flex justify-between pt-2 border-t border-slate-200">
              <span className="font-semibold text-gray-900">Net Transaction Amount:</span>
              <span className="font-bold text-gray-900">{formatINR(summaryData.selected_net)}</span>
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-2">
            <button
              type="button"
              disabled={isCommitting}
              onClick={() => setSubScreen('review')}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isCommitting || summaryData.selected_rows === 0}
              onClick={handleExecuteCommit}
              className="px-5 py-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg shadow-sm inline-flex items-center space-x-2"
            >
              {isCommitting && <RefreshCw className="w-4 h-4 animate-spin" />}
              <span>Confirm &amp; Import Transactions</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (subScreen === 'results' && commitResult) {
    const s = commitResult.summary;
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="bg-white rounded-2xl border border-emerald-200 p-6 shadow-sm space-y-5">
          <div className="flex items-start space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0">
              <FileCheck2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Import Completed</h2>
              <p className="text-sm text-emerald-700 mt-0.5">{commitResult.message}</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 text-xs">
            <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200">
              <div className="text-emerald-700">Imported</div>
              <div className="text-xl font-bold text-emerald-900">{commitResult.imported_count}</div>
            </div>
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
              <div className="text-gray-600">Skipped</div>
              <div className="text-xl font-bold text-gray-800">{commitResult.skipped_count}</div>
            </div>
            <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
              <div className="text-blue-700">Net Posted</div>
              <div className="text-xl font-bold text-blue-900">{formatINR(s.imported_net)}</div>
            </div>
          </div>

          <div className="p-4 bg-gray-50 rounded-xl border border-gray-200 text-xs space-y-1.5">
            <div className="flex justify-between">
              <span className="text-gray-600">Total Imported Income:</span>
              <span className="font-bold text-emerald-700">+{formatINR(s.imported_income)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Total Imported Expenses:</span>
              <span className="font-bold text-rose-700">-{formatINR(s.imported_expenses)}</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => onNavigate('transactions')}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg"
            >
              View Imported Transactions
            </button>
            <button
              type="button"
              onClick={() => onNavigate('accounts')}
              className="px-4 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-lg"
            >
              View Account Balances
            </button>
            <button
              type="button"
              onClick={() => handleOpenDetails(commitResult.batch)}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-lg"
            >
              View Import Details
            </button>
            <button
              type="button"
              onClick={() => setSubScreen('center')}
              className="ml-auto text-xs text-gray-500 hover:text-gray-800 underline"
            >
              Return to Import Center
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (subScreen === 'details' && activeBatch) {
    return (
      <div className="space-y-6">
        <button
          type="button"
          onClick={() => {
            setSubScreen('center');
            loadCenterData();
          }}
          className="text-xs text-gray-500 hover:text-gray-800 inline-flex items-center space-x-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Imports</span>
        </button>

        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <h2 className="text-xl font-bold text-gray-900">
                Import Details — {activeBatch.original_filename}
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Account: <strong>{activeBatch.account_name}</strong> • Format:{' '}
                {activeBatch.file_type.toUpperCase()} • Uploaded {formatDate(activeBatch.created_at)}
              </p>
            </div>
            {renderBatchStatusBadge(activeBatch.status)}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
              <div className="text-gray-500">Total Rows</div>
              <div className="text-lg font-bold text-gray-900">{activeBatch.total_rows}</div>
            </div>
            <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200">
              <div className="text-emerald-700">Imported</div>
              <div className="text-lg font-bold text-emerald-900">{activeBatch.imported_rows}</div>
            </div>
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
              <div className="text-gray-500">Skipped / Dup</div>
              <div className="text-lg font-bold text-gray-800">{activeBatch.skipped_rows}</div>
            </div>
            <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
              <div className="text-blue-700">SHA-256 Digest</div>
              <div className="text-[11px] font-mono text-blue-900 truncate" title={activeBatch.file_hash}>
                {activeBatch.file_hash.slice(0, 16)}...
              </div>
            </div>
          </div>

          {/* Lifecycle Timeline */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-2">
              Import Lifecycle History
            </h3>
            <div className="space-y-1.5">
              {activeBatch.lifecycle_history.map((evt, idx) => (
                <div
                  key={idx}
                  className="text-xs bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 flex items-center justify-between"
                >
                  <div>
                    <span className="font-semibold uppercase text-gray-800">{evt.to}</span>
                    {evt.note && <span className="text-gray-600 ml-2">— {evt.note}</span>}
                  </div>
                  <span className="text-[11px] text-gray-400">{formatDate(evt.at)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Row-level audit table */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-2">
              Row Audit Records ({detailsRows.length})
            </h3>
            <div className="overflow-x-auto border border-gray-200 rounded-xl">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 border-b border-gray-200 text-gray-600">
                  <tr>
                    <th className="py-2 px-3">Row</th>
                    <th className="py-2 px-3">Date</th>
                    <th className="py-2 px-3">Description</th>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3 text-right">Amount</th>
                    <th className="py-2 px-3">Ledger Transaction Ref</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {detailsRows.map((r) => (
                    <tr key={r.id}>
                      <td className="py-2 px-3 font-mono text-gray-500">#{r.source_row_number}</td>
                      <td className="py-2 px-3">{r.normalized_date ? formatDate(r.normalized_date) : '—'}</td>
                      <td className="py-2 px-3 font-medium text-gray-900">
                        {r.normalized_description || '—'}
                      </td>
                      <td className="py-2 px-3 uppercase text-[10px] font-bold text-gray-600">
                        {r.validation_status}
                      </td>
                      <td className="py-2 px-3 text-right font-semibold">
                        {r.normalized_amount ? formatINR(r.normalized_amount) : '—'}
                      </td>
                      <td className="py-2 px-3 font-mono text-[11px] text-gray-500">
                        {r.imported_transaction_id ? r.imported_transaction_id.slice(0, 8) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Screen 1 — Import Center (Default)
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Imports</h1>
          <p className="text-sm text-gray-600 mt-1">
            Upload CSV or XLSX bank statements, validate rows, detect duplicates, and post to your
            double-entry ledger.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <span className="hidden sm:inline-block text-xs text-gray-500 bg-gray-100 px-2.5 py-1.5 rounded-lg">
            CSV (UTF-8 / BOM) &amp; XLSX • Max 10 MB
          </span>
          <button
            type="button"
            onClick={() => {
              setUploadError(null);
              setSelectedFile(null);
              setUploadProgress(0);
              setIsUploadOpen(true);
            }}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Statement</span>
          </button>
        </div>
      </div>

      {/* Overview Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
          <div className="text-xs font-semibold text-gray-500 uppercase">Total Imports</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">
            {overview?.total_imports ?? 0}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
          <div className="text-xs font-semibold text-gray-500 uppercase">Completed</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">
            {overview?.completed_imports ?? 0}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
          <div className="text-xs font-semibold text-gray-500 uppercase">Failed</div>
          <div className="text-2xl font-bold text-rose-600 mt-1">
            {overview?.failed_imports ?? 0}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
          <div className="text-xs font-semibold text-gray-500 uppercase">
            Transactions Imported
          </div>
          <div className="text-2xl font-bold text-blue-600 mt-1">
            {overview?.transactions_imported ?? 0}
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center space-x-3 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" />
          <div className="flex-1">{error}</div>
          <button onClick={loadCenterData} className="underline font-medium">
            Retry
          </button>
        </div>
      )}

      {!isLoading && accounts.length === 0 && (
        <WorkspaceStarterBanner
          title="Add or connect an account before importing a statement"
          description="Imported CSV/XLSX transactions post directly into a destination account in your ledger. Connect a bank or create your first account below."
          onNavigate={onNavigate}
        />
      )}

      {/* Import History Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">Import History</h2>
          <button
            type="button"
            onClick={loadCenterData}
            disabled={isLoading}
            className="text-gray-500 hover:text-gray-700 p-1.5 rounded-lg hover:bg-gray-100"
            title="Refresh Imports"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-500 text-sm">Loading import history...</div>
        ) : !overview || overview.batches.length === 0 ? (
          <div className="p-12 text-center">
            <FileSpreadsheet className="w-12 h-12 mx-auto text-gray-300 mb-3" />
            <h3 className="text-base font-semibold text-gray-900">No bank statements uploaded yet</h3>
            <p className="text-sm text-gray-500 mt-1 max-w-md mx-auto">
              Upload a CSV or Excel (.xlsx) bank statement to review, categorize, and import your
              transactions safely.
            </p>
            <button
              type="button"
              onClick={() => setIsUploadOpen(true)}
              className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm"
            >
              + Upload First Statement
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs font-semibold text-gray-500 uppercase border-b border-gray-200">
                <tr>
                  <th className="py-3 px-4">Filename</th>
                  <th className="py-3 px-4">Account</th>
                  <th className="py-3 px-4">Upload Date</th>
                  <th className="py-3 px-4">Format</th>
                  <th className="py-3 px-4">Rows / Imported</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                {overview.batches.map((b) => (
                  <tr key={b.id} className="hover:bg-gray-50/70">
                    <td className="py-3 px-4 font-semibold text-gray-900">
                      {b.original_filename}
                    </td>
                    <td className="py-3 px-4 text-gray-700">{b.account_name || 'Account'}</td>
                    <td className="py-3 px-4 text-gray-500">{formatDate(b.created_at)}</td>
                    <td className="py-3 px-4 uppercase font-mono text-gray-600">{b.file_type}</td>
                    <td className="py-3 px-4">
                      {b.total_rows} total / <strong>{b.imported_rows} imported</strong>
                    </td>
                    <td className="py-3 px-4">{renderBatchStatusBadge(b.status)}</td>
                    <td className="py-3 px-4 text-right space-x-2 whitespace-nowrap">
                      {(b.status === 'mapping_required' ||
                        b.status === 'ready_for_review' ||
                        b.status === 'uploaded') && (
                        <button
                          type="button"
                          onClick={() => handleOpenBatch(b)}
                          className="px-2.5 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded font-medium inline-flex items-center space-x-1"
                        >
                          <Play className="w-3 h-3" />
                          <span>
                            {b.status === 'ready_for_review' ? 'Continue Review' : 'Map Columns'}
                          </span>
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleOpenDetails(b)}
                        className="px-2.5 py-1 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded font-medium inline-flex items-center space-x-1"
                      >
                        <Eye className="w-3 h-3" />
                        <span>Details</span>
                      </button>
                      {b.status !== 'completed' && b.status !== 'completed_with_errors' && (
                        <button
                          type="button"
                          onClick={() => handleDeleteBatch(b)}
                          className="p-1 text-gray-400 hover:text-red-600 rounded"
                          title="Cancel & Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Screen 2 — Upload Statement Modal */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl relative">
            <button
              type="button"
              onClick={() => !isUploading && setIsUploadOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-gray-900">Upload Bank Statement</h3>
            <p className="text-xs text-gray-500 mt-1">
              Supported formats: <strong>.csv</strong> (UTF-8 / BOM) and <strong>.xlsx</strong>{' '}
              (Excel). Max size: <strong>10 MB</strong>.
            </p>

            {uploadError && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                <span>{uploadError}</span>
              </div>
            )}

            <form onSubmit={handleUploadSubmit} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Destination Financial Account *
                </label>
                {accounts.length === 0 ? (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                    You need at least one active account before importing.{' '}
                    <button
                      type="button"
                      onClick={() => onNavigate('accounts')}
                      className="underline font-semibold"
                    >
                      Create an Account
                    </button>
                  </div>
                ) : (
                  <select
                    required
                    value={selectedAccountId}
                    onChange={(e) => setSelectedAccountId(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
                  >
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({a.account_type.replace('_', ' ').toUpperCase()} —{' '}
                        {formatINR(a.current_balance)})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Drag and Drop Area */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  const dropped = e.dataTransfer.files?.[0] || null;
                  handleFilePicked(dropped);
                }}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                  isDragging
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-300 hover:border-blue-400 bg-gray-50/70'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx"
                  className="hidden"
                  onChange={(e) => handleFilePicked(e.target.files?.[0] || null)}
                />
                <Upload className="w-8 h-8 mx-auto text-blue-600 mb-2" />
                {selectedFile ? (
                  <div className="text-sm font-semibold text-gray-900 flex items-center justify-center space-x-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>{selectedFile.name}</span>
                    <span className="text-xs font-normal text-gray-500">
                      ({(selectedFile.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                ) : (
                  <>
                    <div className="text-sm font-medium text-gray-800">
                      Drag &amp; drop your bank statement here, or click to browse
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      Accepts .csv and .xlsx files up to 10 MB
                    </div>
                  </>
                )}
              </div>

              {isUploading && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-gray-600">
                    <span>Uploading &amp; inspecting file...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-600 transition-all duration-150"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-600 flex items-start space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <span>
                  Uploaded statements are stored privately on the server, never publicly accessible,
                  and strictly isolated to your account.
                </span>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  disabled={isUploading}
                  onClick={() => setIsUploadOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !selectedFile || accounts.length === 0}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg shadow-sm inline-flex items-center space-x-1.5"
                >
                  {isUploading && <RefreshCw className="w-4 h-4 animate-spin" />}
                  <span>Upload &amp; Inspect</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
