import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Download,
  Eye,
  FolderOpen,
  Grid,
  List,
  Mail,
  MessageSquareWarning,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from 'lucide-react';
import { documentsApi, emailIngestionApi } from '../../services/documentsApi';
import {
  DocumentCategory,
  DocumentOverview,
  DocumentProcessingJob,
  EmailCandidate,
  EmailConnection,
  EmailSyncHistoryItem,
  FinancialDocumentSummary,
  SmsIngestionStatus,
} from '../../types/documents';
import { formatDate, formatINR } from '../../lib/formatters';
import { OcrReviewModal } from './OcrReviewModal';

interface DocumentsPageProps {
  onNavigate: (view: string) => void;
}

type DocTab = 'overview' | 'library' | 'upload' | 'review' | 'email' | 'history';

export const DOCUMENT_CATEGORY_OPTIONS: { id: DocumentCategory; label: string }[] = [
  { id: 'electricity_bill', label: 'Electricity Bill' },
  { id: 'water_bill', label: 'Water Bill' },
  { id: 'gas_bill', label: 'Gas Bill' },
  { id: 'internet_bill', label: 'Internet & Broadband' },
  { id: 'mobile_bill', label: 'Mobile Bill' },
  { id: 'credit_card_statement', label: 'Credit Card Statement' },
  { id: 'bank_statement', label: 'Bank Statement' },
  { id: 'shopping_receipt', label: 'Shopping Receipt' },
  { id: 'travel_receipt', label: 'Travel Receipt' },
  { id: 'medical_receipt', label: 'Medical Receipt' },
  { id: 'insurance', label: 'Insurance Document' },
  { id: 'tax', label: 'Tax Document' },
  { id: 'loan', label: 'Loan Document' },
  { id: 'subscription_invoice', label: 'Subscription Invoice' },
  { id: 'other', label: 'Other Financial Document' },
];

export const DocumentsPage: React.FC<DocumentsPageProps> = () => {
  const [tab, setTab] = useState<DocTab>('overview');
  const [overview, setOverview] = useState<DocumentOverview | null>(null);
  const [docs, setDocs] = useState<FinancialDocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Library Filters
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Upload State
  const [uploadCategory, setUploadCategory] = useState<DocumentCategory>('electricity_bill');
  const [autoProcess, setAutoProcess] = useState(true);
  const [dragActive, setDragActive] = useState(false);
  const [uploadResults, setUploadResults] = useState<
    { filename: string; status: 'uploading' | 'ok' | 'error'; message?: string; id?: string }[]
  >([]);

  // Email & SMS Ingestion State
  const [gmailConn, setGmailConn] = useState<EmailConnection | null>(null);
  const [syncHistory, setSyncHistory] = useState<EmailSyncHistoryItem[]>([]);
  const [candidates, setCandidates] = useState<EmailCandidate[]>([]);
  const [smsStatus, setSmsStatus] = useState<SmsIngestionStatus | null>(null);
  const [syncQuery, setSyncQuery] = useState('');
  const [syncing, setSyncing] = useState(false);

  // Processing History
  const [jobs, setJobs] = useState<DocumentProcessingJob[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [reviewDocId, setReviewDocId] = useState<string | null>(null);

  const loadAll = async (silent: boolean = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const effectiveStatus = tab === 'review' ? 'needs_review' : statusFilter || undefined;
      const [ov, listRes, histRes, connsRes, syncRes, candRes, smsRes] = await Promise.all([
        documentsApi.getOverview(),
        documentsApi.listDocuments({
          category: catFilter || undefined,
          status_filter: effectiveStatus,
          search: search.trim() || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          page,
          page_size: 12,
        }),
        documentsApi.listProcessingHistory(),
        emailIngestionApi.getConnections(),
        emailIngestionApi.listSyncHistory(),
        emailIngestionApi.listCandidates(),
        emailIngestionApi.getSmsStatus(),
      ]);
      setOverview(ov);
      setDocs(listRes.items);
      setTotal(listRes.total);
      setTotalPages(listRes.total_pages);
      setJobs(histRes.items);
      setGmailConn(connsRes[0] || null);
      setSyncHistory(syncRes);
      setCandidates(candRes);
      setSmsStatus(smsRes);

      // Keep recently uploaded batch statuses in sync automatically once OCR completes
      const byId = new Map(listRes.items.map((d) => [d.id, d]));
      setUploadResults((prev) =>
        prev.map((item) => {
          const found = item.id ? byId.get(item.id) : undefined;
          if (!found) return item;
          if (found.processing_status === 'needs_review') {
            return {
              ...item,
              message: `OCR ready (${found.merchant_name || 'Review fields'})`,
            };
          }
          if (found.processing_status === 'failed') {
            return { ...item, status: 'error', message: 'OCR extraction failed' };
          }
          return item;
        })
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load documents workspace.');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, page, catFilter, statusFilter]);

  // Automatically poll silently while any uploaded document is queued or processing OCR
  useEffect(() => {
    const hasPending =
      (overview?.processing_count || 0) > 0 ||
      docs.some((d) => d.processing_status === 'queued' || d.processing_status === 'processing');
    if (!hasPending) return;
    const timer = window.setTimeout(() => {
      void loadAll(true);
    }, 1200);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overview?.processing_count, docs]);

  const handleFilesSelected = async (files: FileList | File[]) => {
    const arr = Array.from(files);
    if (arr.length === 0) return;
    setError(null);
    for (const file of arr) {
      setUploadResults((prev) => [
        { filename: file.name, status: 'uploading' },
        ...prev,
      ]);
      try {
        const res = await documentsApi.uploadDocument(file, uploadCategory, autoProcess);
        setUploadResults((prev) =>
          prev.map((item) =>
            item.filename === file.name && item.status === 'uploading'
              ? {
                  ...item,
                  status: 'ok',
                  id: res.id,
                  message: res.duplicate_flag
                    ? 'Uploaded (duplicate SHA-256 hash flagged)'
                    : `Uploaded (${res.processing_status})`,
                }
              : item
          )
        );
      } catch (err) {
        setUploadResults((prev) =>
          prev.map((item) =>
            item.filename === file.name && item.status === 'uploading'
              ? {
                  ...item,
                  status: 'error',
                  message: err instanceof Error ? err.message : 'Upload failed',
                }
              : item
          )
        );
      }
    }
    await loadAll();
  };

  const handleConnectGmail = async () => {
    setError(null);
    try {
      const res = await emailIngestionApi.getGmailConnectUrl();
      window.location.href = res.authorization_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Gmail OAuth unavailable.');
    }
  };

  const handleDisconnectGmail = async () => {
    setError(null);
    try {
      await emailIngestionApi.disconnectGmail();
      setBanner('Gmail disconnected and OAuth tokens revoked/removed.');
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to disconnect Gmail.');
    }
  };

  const handleSyncGmail = async () => {
    if (syncing) return;
    setSyncing(true);
    setError(null);
    try {
      const res = await emailIngestionApi.syncGmail({
        search_query: syncQuery.trim() || undefined,
      });
      setBanner(
        `Sync ${res.status}: scanned ${res.messages_scanned} messages, processed ${res.attachments_processed} attachments, ${res.candidates_needing_review} ready for review.`
      );
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Gmail synchronization failed.');
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      await documentsApi.deleteDocument(docId);
      setBanner('Document and stored file deleted cleanly.');
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete document.');
    }
  };

  const handleDownloadDoc = async (doc: FinancialDocumentSummary) => {
    try {
      const blob = await documentsApi.fetchDownloadBlob(doc.id);
      if (typeof URL.createObjectURL === 'function') {
        const u = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = u;
        a.download = doc.original_filename;
        a.click();
        URL.revokeObjectURL(u);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed.');
    }
  };

  const statusPill = (st: string) => {
    const map: Record<string, string> = {
      confirmed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      needs_review: 'bg-amber-50 text-amber-800 border-amber-200',
      extracted: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      processing: 'bg-blue-50 text-blue-700 border-blue-200',
      queued: 'bg-sky-50 text-sky-700 border-sky-200',
      uploaded: 'bg-gray-100 text-gray-700 border-gray-200',
      rejected: 'bg-rose-50 text-rose-700 border-rose-200',
      failed: 'bg-red-100 text-red-800 border-red-300',
      duplicate_warning: 'bg-amber-100 text-amber-900 border-amber-300',
    };
    return (
      <span
        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
          map[st] || 'bg-gray-100 text-gray-700 border-gray-200'
        }`}
      >
        {st.replace('_', ' ')}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Documents, OCR &amp; Email Ingestion
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Private financial vault with local CPU OCR, Indian GST extraction, human verification,
            and read-only Gmail bill sync.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void loadAll()}
            className="px-3 py-2 bg-white border border-gray-200 hover:bg-gray-50 rounded-lg text-xs font-semibold inline-flex items-center space-x-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            onClick={() => setTab('upload')}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium inline-flex items-center space-x-1.5 shadow-sm"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Documents</span>
          </button>
        </div>
      </div>

      {banner && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-900 flex justify-between">
          <span>{banner}</span>
          <button type="button" onClick={() => setBanner(null)} className="underline font-semibold">
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => void loadAll()} className="underline font-semibold">
            Retry
          </button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="border-b border-gray-200 flex flex-wrap gap-1">
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'library', label: `All Documents (${overview?.total_documents ?? total})` },
          { id: 'upload', label: 'Upload Documents' },
          { id: 'review', label: `Needs Review (${overview?.needs_review_count ?? 0})` },
          { id: 'email', label: `Email Imports (${candidates.length})` },
          { id: 'history', label: `Processing History (${jobs.length})` },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setTab(t.id as DocTab);
              setPage(1);
            }}
            className={`px-3.5 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
              tab === t.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* A. OVERVIEW TAB */}
      {tab === 'overview' && overview && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <div className="text-[11px] font-semibold uppercase text-gray-500">Total Documents</div>
              <div className="text-2xl font-bold text-gray-900 mt-1">{overview.total_documents}</div>
            </div>
            <div className="bg-white rounded-xl border border-emerald-200 p-4 shadow-sm">
              <div className="text-[11px] font-semibold uppercase text-emerald-700">Processed</div>
              <div className="text-2xl font-bold text-emerald-700 mt-1">{overview.processed_count}</div>
            </div>
            <div className="bg-white rounded-xl border border-amber-200 p-4 shadow-sm">
              <div className="text-[11px] font-semibold uppercase text-amber-700">Awaiting Review</div>
              <div className="text-2xl font-bold text-amber-700 mt-1">
                {overview.needs_review_count}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-blue-200 p-4 shadow-sm">
              <div className="text-[11px] font-semibold uppercase text-blue-700">Processing</div>
              <div className="text-2xl font-bold text-blue-700 mt-1">{overview.processing_count}</div>
            </div>
            <div className="bg-white rounded-xl border border-rose-200 p-4 shadow-sm">
              <div className="text-[11px] font-semibold uppercase text-rose-700">Failed</div>
              <div className="text-2xl font-bold text-rose-700 mt-1">{overview.failed_count}</div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm text-xs space-y-3">
            <div className="flex justify-between items-center">
              <span className="font-bold text-gray-900 text-sm">Recently Uploaded Documents</span>
              <button
                type="button"
                onClick={() => setTab('library')}
                className="text-blue-600 hover:underline font-medium"
              >
                View All Documents →
              </button>
            </div>
            {overview.recent_documents.length === 0 ? (
              <div className="py-8 text-center text-gray-400">
                <FolderOpen className="w-10 h-10 mx-auto mb-2 text-gray-300" />
                No private financial documents uploaded yet.
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {overview.recent_documents.map((d) => (
                  <div
                    key={d.id}
                    onClick={() => setReviewDocId(d.id)}
                    className="py-2.5 flex flex-wrap items-center justify-between gap-2 cursor-pointer hover:bg-slate-50 px-2 rounded-lg"
                  >
                    <div>
                      <div className="font-semibold text-gray-900">{d.original_filename}</div>
                      <div className="text-[11px] text-gray-500">
                        {d.merchant_name || d.document_category.replace('_', ' ')} •{' '}
                        {d.grand_total ? formatINR(d.grand_total) : 'Amount pending review'}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {statusPill(d.processing_status)}
                      <span className="text-blue-600 font-semibold">Review</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* B & D. DOCUMENT LIBRARY & NEEDS REVIEW QUEUE */}
      {(tab === 'library' || tab === 'review') && (
        <div className="space-y-4 text-xs">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              void loadAll();
            }}
            className="bg-white p-3.5 rounded-xl border border-gray-200 flex flex-wrap items-center gap-2"
          >
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search filename, merchant, invoice #, GSTIN..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 border border-gray-300 rounded-lg"
              />
            </div>
            <select
              value={catFilter}
              onChange={(e) => setCatFilter(e.target.value)}
              className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Categories</option>
              {DOCUMENT_CATEGORY_OPTIONS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            {tab === 'library' && (
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
              >
                <option value="">All Statuses</option>
                <option value="needs_review">Needs Review</option>
                <option value="confirmed">Confirmed</option>
                <option value="queued">Queued</option>
                <option value="processing">Processing</option>
                <option value="rejected">Rejected</option>
                <option value="failed">Failed</option>
              </select>
            )}
            <input
              type="date"
              aria-label="From date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="px-2 py-1.5 border border-gray-300 rounded-lg"
            />
            <input
              type="date"
              aria-label="To date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="px-2 py-1.5 border border-gray-300 rounded-lg"
            />
            <button type="submit" className="px-3 py-1.5 bg-slate-900 text-white rounded-lg">
              Apply
            </button>
            <div className="flex border border-gray-200 rounded-lg overflow-hidden ml-auto">
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className={`p-1.5 ${viewMode === 'grid' ? 'bg-blue-50 text-blue-600' : 'bg-white text-gray-500'}`}
                title="Grid view"
              >
                <Grid className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode('list')}
                className={`p-1.5 ${viewMode === 'list' ? 'bg-blue-50 text-blue-600' : 'bg-white text-gray-500'}`}
                title="List view"
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>
          </form>

          {docs.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-10 text-center text-gray-400">
              No matching documents found.
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {docs.map((d) => (
                <div
                  key={d.id}
                  onClick={() => setReviewDocId(d.id)}
                  className="bg-white rounded-2xl border border-gray-200 hover:border-blue-300 shadow-sm hover:shadow-md transition-all p-4 flex flex-col justify-between cursor-pointer"
                >
                  <div className="space-y-2.5">
                    <div className="flex justify-between items-start gap-2">
                      <div className="flex items-start space-x-2.5 min-w-0">
                        <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 font-extrabold flex items-center justify-center uppercase text-[10px] flex-shrink-0">
                          {d.file_type}
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-gray-900 truncate">{d.original_filename}</div>
                          <div className="text-[11px] text-gray-500 truncate">
                            {d.merchant_name || d.document_category.replace('_', ' ')}
                          </div>
                        </div>
                      </div>
                      {statusPill(d.processing_status)}
                    </div>

                    <div className="grid grid-cols-2 gap-2 bg-slate-50 p-2.5 rounded-xl">
                      <div>
                        <div className="text-[10px] text-gray-500 uppercase">Extracted Total</div>
                        <div className="font-bold text-gray-900">
                          {d.grand_total ? formatINR(d.grand_total) : 'Pending / Unset'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-gray-500 uppercase">Uploaded</div>
                        <div className="font-medium text-gray-700">{formatDate(d.uploaded_at.slice(0, 10))}</div>
                      </div>
                    </div>

                    {d.links.length > 0 && (
                      <div className="text-[11px] text-emerald-700 font-medium">
                        Linked to {d.links.map((l) => l.target_label || l.target_type).join(', ')}
                      </div>
                    )}
                  </div>

                  <div
                    className="mt-3 pt-2.5 border-t border-gray-100 flex justify-between items-center"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      onClick={() => setReviewDocId(d.id)}
                      className="px-3 py-1 bg-blue-600 text-white rounded-lg font-semibold inline-flex items-center space-x-1"
                    >
                      <Eye className="w-3 h-3" />
                      <span>Review &amp; Extract</span>
                    </button>
                    <div className="flex space-x-1.5">
                      <button
                        type="button"
                        onClick={() => void handleDownloadDoc(d)}
                        className="p-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700"
                        title="Download"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDeleteDoc(d.id)}
                        className="p-1.5 bg-rose-50 hover:bg-rose-100 rounded-lg text-rose-600"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-gray-50 border-b text-[10px] uppercase text-gray-600">
                  <tr>
                    <th className="py-2.5 px-4">Document</th>
                    <th className="py-2.5 px-3">Category</th>
                    <th className="py-2.5 px-3">Merchant</th>
                    <th className="py-2.5 px-3 text-right">Amount</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {docs.map((d) => (
                    <tr key={d.id} className="hover:bg-gray-50">
                      <td className="py-2.5 px-4 font-semibold">{d.original_filename}</td>
                      <td className="py-2.5 px-3 uppercase text-[10px]">{d.document_category}</td>
                      <td className="py-2.5 px-3">{d.merchant_name || '—'}</td>
                      <td className="py-2.5 px-3 text-right font-mono">
                        {d.grand_total ? formatINR(d.grand_total) : '—'}
                      </td>
                      <td className="py-2.5 px-3">{statusPill(d.processing_status)}</td>
                      <td className="py-2.5 px-4 text-right space-x-2">
                        <button
                          type="button"
                          onClick={() => setReviewDocId(d.id)}
                          className="text-blue-600 font-semibold hover:underline"
                        >
                          Review
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeleteDoc(d.id)}
                          className="text-rose-600 hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex justify-between items-center bg-white px-4 py-2.5 rounded-xl border border-gray-200">
              <span>
                Total {total} • Page {page} of {totalPages}
              </span>
              <div className="space-x-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-2.5 py-1 border rounded disabled:opacity-50"
                >
                  Prev
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-2.5 py-1 border rounded disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* C. UPLOAD DOCUMENTS TAB */}
      {tab === 'upload' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Document Category</label>
              <select
                aria-label="Upload Document Category"
                value={uploadCategory}
                onChange={(e) => setUploadCategory(e.target.value as DocumentCategory)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
              >
                {DOCUMENT_CATEGORY_OPTIONS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center space-x-2 cursor-pointer p-2 bg-slate-50 border border-slate-200 rounded-lg w-full">
                <input
                  type="checkbox"
                  checked={autoProcess}
                  onChange={(e) => setAutoProcess(e.target.checked)}
                />
                <span className="font-medium text-gray-800">
                  Run local OCR &amp; Indian GST extraction automatically
                </span>
              </label>
            </div>
          </div>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragActive(false);
              if (e.dataTransfer.files) void handleFilesSelected(e.dataTransfer.files);
            }}
            className={`border-2 border-dashed rounded-2xl p-10 text-center transition-colors ${
              dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-slate-50/70'
            }`}
          >
            <Upload className="w-10 h-10 text-blue-600 mx-auto mb-3" />
            <div className="text-sm font-bold text-gray-900">
              Drag &amp; drop bills, GST invoices, receipts or statements
            </div>
            <p className="text-gray-500 mt-1">
              Supports PDF (digital or scanned multi-page), JPG, JPEG, PNG, and WebP up to 15 MB.
            </p>
            <label className="mt-4 inline-block px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold cursor-pointer">
              Select Files
              <input
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.webp"
                onChange={(e) => {
                  if (e.target.files) void handleFilesSelected(e.target.files);
                }}
                className="hidden"
              />
            </label>
          </div>

          {uploadResults.length > 0 && (
            <div className="space-y-2 pt-2">
              <div className="font-bold text-gray-800">Upload Batch Status</div>
              {uploadResults.map((r, i) => (
                <div
                  key={`${r.filename}-${i}`}
                  className="p-2.5 rounded-lg border border-gray-200 flex justify-between items-center"
                >
                  <span className="font-medium">{r.filename}</span>
                  <div className="flex items-center space-x-2">
                    <span
                      className={
                        r.status === 'error'
                          ? 'text-rose-600 font-semibold'
                          : r.status === 'ok'
                            ? 'text-emerald-700 font-semibold'
                            : 'text-blue-600'
                      }
                    >
                      {r.status === 'uploading' ? 'Uploading...' : r.message}
                    </span>
                    {r.id && (
                      <button
                        type="button"
                        onClick={() => setReviewDocId(r.id!)}
                        className="px-2 py-1 bg-blue-50 text-blue-700 rounded font-semibold"
                      >
                        Open Review
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* E. EMAIL & SMS INGESTION TAB */}
      {tab === 'email' && (
        <div className="space-y-5 text-xs">
          {/* Gmail OAuth Connection Card */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center">
                  <Mail className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-900">
                    Gmail Bill &amp; Invoice Sync (Read-Only OAuth 2.0)
                  </h3>
                  <div className="text-gray-500">
                    Status:{' '}
                    <strong className="uppercase">{gmailConn?.status || 'disconnected'}</strong>
                    {gmailConn?.email_address ? ` • ${gmailConn.email_address}` : ''}
                    {gmailConn?.last_sync_at
                      ? ` • Last sync: ${new Date(gmailConn.last_sync_at).toLocaleString()}`
                      : ''}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {gmailConn?.status === 'connected' ? (
                  <>
                    <button
                      type="button"
                      disabled={syncing}
                      onClick={() => void handleSyncGmail()}
                      className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold inline-flex items-center space-x-1.5"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                      <span>Sync Now</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDisconnectGmail()}
                      className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg font-semibold"
                    >
                      Disconnect Gmail
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => void handleConnectGmail()}
                    className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg font-semibold"
                  >
                    Connect Gmail Account
                  </button>
                )}
              </div>
            </div>

            {gmailConn && !gmailConn.oauth_configured && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 flex items-start space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <span>
                  Google OAuth credentials (<code>GOOGLE_OAUTH_CLIENT_ID</code> /{' '}
                  <code>GOOGLE_OAUTH_CLIENT_SECRET</code>) are not configured on this server yet.
                  Configure credentials in backend environment to authorize live Gmail mailboxes.
                </span>
              </div>
            )}

            {gmailConn?.status === 'connected' && (
              <div className="flex gap-2 pt-1">
                <input
                  type="text"
                  placeholder="Optional search filter (defaults to financial bills, invoices & statements)"
                  value={syncQuery}
                  onChange={(e) => setSyncQuery(e.target.value)}
                  className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg"
                />
              </div>
            )}
          </div>

          {/* Synced Email Candidates */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm space-y-3">
            <div className="font-bold text-gray-900 text-sm">
              Imported Email Candidates Requiring Review ({candidates.length})
            </div>
            {candidates.length === 0 ? (
              <p className="text-gray-400 py-4 text-center">No email candidates synchronized yet.</p>
            ) : (
              <div className="divide-y divide-gray-100">
                {candidates.map((c) => (
                  <div key={c.id} className="py-3 flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-0.5 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-gray-900">
                          {c.merchant_name || c.message?.subject || 'Email Candidate'}
                        </span>
                        {statusPill(c.status)}
                        {c.duplicate_status !== 'unique' && (
                          <span className="px-1.5 py-0.5 bg-amber-100 text-amber-900 rounded text-[10px] font-semibold">
                            {c.duplicate_reason || c.duplicate_status}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-gray-500">
                        From: {c.message?.sender || 'Unknown'} • Invoice: {c.invoice_number || '—'} •
                        Amount: {c.amount ? formatINR(c.amount) : 'Pending review'}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {c.document_id && (
                        <button
                          type="button"
                          onClick={() => setReviewDocId(c.document_id!)}
                          className="px-2.5 py-1 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded font-semibold"
                        >
                          Inspect Attachment
                        </button>
                      )}
                      {c.status !== 'confirmed' && c.status !== 'rejected' && (
                        <>
                          <button
                            type="button"
                            onClick={async () => {
                              await emailIngestionApi.confirmCandidate(c.id, { action: 'standalone' });
                              setBanner('Email candidate confirmed cleanly.');
                              await loadAll();
                            }}
                            className="px-2.5 py-1 bg-emerald-600 text-white rounded font-semibold"
                          >
                            Confirm
                          </button>
                          <button
                            type="button"
                            onClick={async () => {
                              await emailIngestionApi.rejectCandidate(c.id, 'Dismissed by user');
                              setBanner('Email candidate rejected.');
                              await loadAll();
                            }}
                            className="px-2.5 py-1 bg-rose-50 text-rose-700 border border-rose-200 rounded font-semibold"
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sync History */}
          {syncHistory.length > 0 && (
            <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm space-y-2">
              <div className="font-bold text-gray-900">Synchronization History</div>
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="bg-gray-50 text-[10px] uppercase text-gray-500 border-b">
                    <tr>
                      <th className="py-2 px-3">Started</th>
                      <th className="py-2 px-3">Mode</th>
                      <th className="py-2 px-3">Status</th>
                      <th className="py-2 px-3 text-right">Scanned</th>
                      <th className="py-2 px-3 text-right">Relevant</th>
                      <th className="py-2 px-3 text-right">Attachments</th>
                      <th className="py-2 px-3 text-right">Duplicates</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {syncHistory.map((h) => (
                      <tr key={h.id}>
                        <td className="py-2 px-3">{new Date(h.started_at).toLocaleString()}</td>
                        <td className="py-2 px-3">{h.sync_mode}</td>
                        <td className="py-2 px-3">{statusPill(h.status)}</td>
                        <td className="py-2 px-3 text-right">{h.messages_scanned}</td>
                        <td className="py-2 px-3 text-right">{h.relevant_messages}</td>
                        <td className="py-2 px-3 text-right">{h.attachments_processed}</td>
                        <td className="py-2 px-3 text-right">{h.duplicate_candidates}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Module D: SMS Integration Boundary */}
          {smsStatus && (
            <div className="bg-slate-50 rounded-2xl border border-slate-200 p-4 space-y-1.5">
              <div className="flex items-center justify-between">
                <div className="font-bold text-slate-900 flex items-center space-x-2">
                  <MessageSquareWarning className="w-4 h-4 text-slate-600" />
                  <span>Incoming SMS Extraction Boundary</span>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-200 text-slate-700 uppercase">
                  {smsStatus.available ? 'Active' : 'Unavailable (Web SaaS)'}
                </span>
              </div>
              <p className="text-slate-600">{smsStatus.limitation_reason}</p>
              <p className="text-[11px] text-slate-500">{smsStatus.supported_platforms_note}</p>
            </div>
          )}
        </div>
      )}

      {/* F. PROCESSING HISTORY TAB */}
      {tab === 'history' && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto text-xs">
          {jobs.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No OCR processing jobs recorded yet.</div>
          ) : (
            <table className="w-full text-left">
              <thead className="bg-gray-50 border-b text-[10px] uppercase text-gray-600">
                <tr>
                  <th className="py-2.5 px-4">Document</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Attempts</th>
                  <th className="py-2.5 px-3">Started</th>
                  <th className="py-2.5 px-3">Completed</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td className="py-2.5 px-4 font-semibold">
                      {j.document_filename || j.document_id}
                    </td>
                    <td className="py-2.5 px-3">{j.job_type}</td>
                    <td className="py-2.5 px-3">
                      {j.attempt_count}/{j.max_attempts}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500">
                      {j.started_at ? new Date(j.started_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500">
                      {j.completed_at ? new Date(j.completed_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      {statusPill(j.status)}
                      {j.error_message && (
                        <div className="text-[10px] text-rose-600 mt-0.5 max-w-xs truncate">
                          {j.error_message}
                        </div>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      {j.status === 'failed' && (
                        <button
                          type="button"
                          onClick={async () => {
                            await documentsApi.processDocument(j.document_id);
                            setBanner('Re-queued document OCR job.');
                            await loadAll();
                          }}
                          className="px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded font-semibold"
                        >
                          Retry OCR
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <OcrReviewModal
        documentId={reviewDocId}
        onClose={() => setReviewDocId(null)}
        onUpdated={() => void loadAll()}
      />
    </div>
  );
};
