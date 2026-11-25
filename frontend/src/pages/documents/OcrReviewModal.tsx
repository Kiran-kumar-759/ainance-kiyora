import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Link2,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  X,
  XCircle,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { documentsApi } from '../../services/documentsApi';
import { financeApi } from '../../services/financeApi';
import { billsApi } from '../../services/billsApi';
import { loansApi, subscriptionsApi } from '../../services/phase6Api';
import {
  ExtractedLineItem,
  FinancialDocumentDetail,
} from '../../types/documents';
import { FinancialAccount, FinancialTransaction } from '../../types/finance';
import { Bill } from '../../types/bills';
import { Loan, Subscription } from '../../types/phase6';
import { formatDate, formatINR } from '../../lib/formatters';

interface OcrReviewModalProps {
  documentId: string | null;
  onClose: () => void;
  onUpdated: () => void;
}

export const OcrReviewModal: React.FC<OcrReviewModalProps> = ({
  documentId,
  onClose,
  onUpdated,
}) => {
  const [doc, setDoc] = useState<FinancialDocumentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Left preview state
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState(false);

  // Editable extraction state
  const [merchantName, setMerchantName] = useState('');
  const [merchantPhone, setMerchantPhone] = useState('');
  const [merchantAddress, setMerchantAddress] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [invoiceDate, setInvoiceDate] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [paymentDate, setPaymentDate] = useState('');
  const [billPeriod, setBillPeriod] = useState('');
  const [detectedType, setDetectedType] = useState('invoice');
  const [currency, setCurrency] = useState('INR');
  const [subtotal, setSubtotal] = useState('');
  const [taxableAmount, setTaxableAmount] = useState('');
  const [totalTax, setTotalTax] = useState('');
  const [grandTotal, setGrandTotal] = useState('');
  const [amountPaid, setAmountPaid] = useState('');
  const [outstandingAmount, setOutstandingAmount] = useState('');
  const [gstin, setGstin] = useState('');
  const [cgst, setCgst] = useState('');
  const [sgst, setSgst] = useState('');
  const [igst, setIgst] = useState('');
  const [taxPercentage, setTaxPercentage] = useState('');
  const [lineItems, setLineItems] = useState<ExtractedLineItem[]>([]);
  const [decisions, setDecisions] = useState<Record<string, 'accepted' | 'rejected' | 'edited'>>({});

  // Confirm / Link controls
  const [confirmAction, setConfirmAction] = useState<
    | 'standalone'
    | 'create_bill'
    | 'create_transaction'
    | 'link_bill'
    | 'link_transaction'
    | 'link_subscription'
    | 'link_loan'
  >('standalone');
  const [targetId, setTargetId] = useState('');
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectBox, setShowRejectBox] = useState(false);

  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [transactions, setTransactions] = useState<FinancialTransaction[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);

  const populateForm = (d: FinancialDocumentDetail) => {
    const ext = d.extraction;
    setMerchantName(ext?.merchant_name || '');
    setMerchantPhone(ext?.merchant_phone || '');
    setMerchantAddress(ext?.merchant_address || '');
    setInvoiceNumber(ext?.invoice_number || '');
    setInvoiceDate(ext?.invoice_date || '');
    setDueDate(ext?.due_date || '');
    setPaymentDate(ext?.payment_date || '');
    setBillPeriod(ext?.bill_period || '');
    setDetectedType(ext?.detected_document_type || 'invoice');
    setCurrency(ext?.currency || 'INR');
    setSubtotal(ext?.subtotal != null ? String(ext.subtotal) : '');
    setTaxableAmount(ext?.taxable_amount != null ? String(ext.taxable_amount) : '');
    setTotalTax(ext?.total_tax != null ? String(ext.total_tax) : '');
    setGrandTotal(ext?.grand_total != null ? String(ext.grand_total) : '');
    setAmountPaid(ext?.amount_paid != null ? String(ext.amount_paid) : '');
    setOutstandingAmount(ext?.outstanding_amount != null ? String(ext.outstanding_amount) : '');
    setGstin(ext?.gstin || '');
    setCgst(ext?.cgst != null ? String(ext.cgst) : '');
    setSgst(ext?.sgst != null ? String(ext.sgst) : '');
    setIgst(ext?.igst != null ? String(ext.igst) : '');
    setTaxPercentage(ext?.tax_percentage != null ? String(ext.tax_percentage) : '');
    setLineItems(Array.isArray(ext?.line_items) ? ext!.line_items : []);
    setDecisions(ext?.field_decisions || {});
  };

  useEffect(() => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    setBanner(null);
    setPage(1);
    setZoom(100);
    setShowRejectBox(false);
    Promise.all([
      documentsApi.getDocument(documentId),
      financeApi.listAccounts(false).catch(() => []),
      billsApi.listBills({ page_size: 50 }).catch(() => ({ items: [] })),
      financeApi.listTransactions({ page_size: 30 }).catch(() => ({ items: [] })),
      subscriptionsApi.listSubscriptions({ page_size: 50 }).catch(() => ({ items: [] })),
      loansApi.listLoans({ page_size: 50 }).catch(() => ({ items: [] })),
    ])
      .then(([detail, accs, bRes, txRes, subRes, loanRes]) => {
        setDoc(detail);
        setTotalPages(detail.page_count || 1);
        populateForm(detail);
        setAccounts(accs);
        if (accs[0]) setSelectedAccountId(accs[0].id);
        setBills(bRes.items || []);
        setTransactions(txRes.items || []);
        setSubscriptions(subRes.items || []);
        setLoans(loanRes.items || []);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load document.'))
      .finally(() => setLoading(false));
  }, [documentId]);

  useEffect(() => {
    if (!documentId) return;
    let revokedUrl: string | null = null;
    documentsApi
      .fetchPreviewBlob(documentId, page)
      .then(({ blob, totalPages: tp }) => {
        setTotalPages(tp);
        if (typeof URL.createObjectURL === 'function') {
          revokedUrl = URL.createObjectURL(blob);
          setPreviewUrl(revokedUrl);
        }
      })
      .catch(() => setPreviewUrl(null));
    return () => {
      if (revokedUrl && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(revokedUrl);
      }
    };
  }, [documentId, page]);

  useEffect(() => {
    if (confirmAction === 'link_bill') setTargetId(bills[0]?.id || '');
    else if (confirmAction === 'link_transaction') setTargetId(transactions[0]?.id || '');
    else if (confirmAction === 'link_subscription') setTargetId(subscriptions[0]?.id || '');
    else if (confirmAction === 'link_loan') setTargetId(loans[0]?.id || '');
    else setTargetId('');
  }, [confirmAction, bills, transactions, subscriptions, loans]);

  if (!documentId) return null;

  const confBadge = (field: string) => {
    const score = doc?.extraction?.field_confidence?.[field];
    const dec = decisions[field];
    return (
      <span className="inline-flex items-center space-x-1">
        {typeof score === 'number' && (
          <span
            className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${
              score >= 0.85
                ? 'bg-emerald-50 text-emerald-700'
                : score >= 0.65
                  ? 'bg-amber-50 text-amber-700'
                  : 'bg-rose-50 text-rose-700'
            }`}
          >
            {Math.round(score * 100)}%
          </span>
        )}
        <button
          type="button"
          onClick={() => setDecisions((p) => ({ ...p, [field]: 'accepted' }))}
          title="Accept extracted value"
          className={`p-0.5 rounded border ${
            dec === 'accepted'
              ? 'bg-emerald-600 text-white border-emerald-600'
              : 'bg-white text-gray-400 border-gray-200 hover:text-emerald-700'
          }`}
        >
          <Check className="w-2.5 h-2.5" />
        </button>
        <button
          type="button"
          onClick={() => setDecisions((p) => ({ ...p, [field]: 'rejected' }))}
          title="Flag / Reject extracted value"
          className={`p-0.5 rounded border ${
            dec === 'rejected'
              ? 'bg-rose-600 text-white border-rose-600'
              : 'bg-white text-gray-400 border-gray-200 hover:text-rose-700'
          }`}
        >
          <X className="w-2.5 h-2.5" />
        </button>
      </span>
    );
  };

  const handleSaveEdits = async () => {
    if (!doc || busy) return;
    setBusy(true);
    setError(null);
    setBanner(null);
    try {
      const updated = await documentsApi.updateExtraction(doc.id, {
        merchant_name: merchantName.trim() || null,
        merchant_phone: merchantPhone.trim() || null,
        merchant_address: merchantAddress.trim() || null,
        invoice_number: invoiceNumber.trim() || null,
        invoice_date: invoiceDate || null,
        due_date: dueDate || null,
        payment_date: paymentDate || null,
        bill_period: billPeriod.trim() || null,
        detected_document_type: detectedType || null,
        currency: currency.trim() || 'INR',
        subtotal: subtotal.trim() ? subtotal.trim() : null,
        taxable_amount: taxableAmount.trim() ? taxableAmount.trim() : null,
        total_tax: totalTax.trim() ? totalTax.trim() : null,
        grand_total: grandTotal.trim() ? grandTotal.trim() : null,
        amount_paid: amountPaid.trim() ? amountPaid.trim() : null,
        outstanding_amount: outstandingAmount.trim() ? outstandingAmount.trim() : null,
        gstin: gstin.trim() ? gstin.trim().toUpperCase() : null,
        cgst: cgst.trim() ? cgst.trim() : null,
        sgst: sgst.trim() ? sgst.trim() : null,
        igst: igst.trim() ? igst.trim() : null,
        tax_percentage: taxPercentage.trim() ? taxPercentage.trim() : null,
        line_items: lineItems.filter((li) => li.description.trim()),
        field_decisions: decisions,
      });
      setDoc(updated);
      populateForm(updated);
      setBanner('Extraction changes saved to audit history.');
      onUpdated();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save changes.');
    } finally {
      setBusy(false);
    }
  };

  const handleConfirm = async () => {
    if (!doc || busy) return;
    setBusy(true);
    setError(null);
    try {
      // Save any pending edits first cleanly
      await documentsApi.updateExtraction(doc.id, {
        merchant_name: merchantName.trim() || null,
        invoice_number: invoiceNumber.trim() || null,
        invoice_date: invoiceDate || null,
        due_date: dueDate || null,
        grand_total: grandTotal.trim() ? grandTotal.trim() : null,
        gstin: gstin.trim() ? gstin.trim().toUpperCase() : null,
        field_decisions: decisions,
      });
      const confirmed = await documentsApi.confirmDocument(doc.id, {
        action: confirmAction,
        target_id: targetId || undefined,
        financial_account_id:
          confirmAction === 'create_transaction' || confirmAction === 'create_bill'
            ? selectedAccountId || undefined
            : undefined,
        amount: grandTotal.trim() ? grandTotal.trim() : undefined,
        due_date: dueDate || undefined,
        bill_name: merchantName.trim() || undefined,
      });
      setDoc(confirmed);
      setBanner('Document confirmed cleanly.');
      onUpdated();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to confirm document.');
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    if (!doc || busy || rejectReason.trim().length < 2) return;
    setBusy(true);
    setError(null);
    try {
      const rejected = await documentsApi.rejectDocument(doc.id, rejectReason.trim());
      setDoc(rejected);
      setShowRejectBox(false);
      setBanner('Document marked as rejected.');
      onUpdated();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to reject document.');
    } finally {
      setBusy(false);
    }
  };

  const handleDownload = async () => {
    if (!doc) return;
    const blob = await documentsApi.fetchDownloadBlob(doc.id);
    if (typeof URL.createObjectURL === 'function') {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.original_filename;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const handleRerunOcr = async () => {
    if (!doc || busy) return;
    setBusy(true);
    setError(null);
    setBanner('Re-running OCR extraction...');
    try {
      await documentsApi.processDocument(doc.id);
      for (let i = 0; i < 15; i += 1) {
        await new Promise((r) => setTimeout(r, 800));
        const latest = await documentsApi.getDocument(doc.id);
        if (latest.ocr_status === 'completed' || latest.ocr_status === 'failed') {
          setDoc(latest);
          populateForm(latest);
          setBanner(
            latest.ocr_status === 'completed'
              ? 'OCR extraction refreshed cleanly.'
              : 'OCR extraction failed. Check processing history.'
          );
          onUpdated();
          return;
        }
      }
      setBanner('OCR job is still running in the background. Click Refresh shortly.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to re-run OCR.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/60 backdrop-blur-xs">
      <div className="bg-white rounded-2xl w-full max-w-6xl h-[92vh] flex flex-col shadow-2xl overflow-hidden text-xs">
        {/* Top Modal Header */}
        <div className="px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center justify-between gap-2 bg-slate-50">
          <div className="flex items-center space-x-2.5">
            <FileText className="w-5 h-5 text-blue-600" />
            <div>
              <h3 className="text-sm font-bold text-gray-900">
                {doc?.original_filename || 'Document Review Workspace'}
              </h3>
              <div className="text-[11px] text-gray-500">
                Status: <strong className="uppercase">{doc?.processing_status}</strong> • OCR:{' '}
                <strong className="uppercase">{doc?.ocr_status}</strong>
                {doc?.duplicate_flag && (
                  <span className="ml-2 px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded font-semibold">
                    Duplicate File Hash Detected
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              disabled={busy}
              onClick={handleRerunOcr}
              className="px-2.5 py-1.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg hover:bg-indigo-100 inline-flex items-center space-x-1 font-semibold disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} />
              <span>Re-run OCR</span>
            </button>
            <button
              type="button"
              onClick={handleDownload}
              className="px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 inline-flex items-center space-x-1 font-medium"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download Original</span>
            </button>
            <button
              type="button"
              aria-label="Close review modal"
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            <RefreshCw className="w-5 h-5 animate-spin mr-2 text-blue-600" />
            Loading document &amp; OCR extraction...
          </div>
        ) : (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 overflow-hidden">
            {/* LEFT PANEL: Original Document Viewer */}
            <div className="bg-slate-900 text-slate-200 flex flex-col overflow-hidden border-r border-gray-200">
              <div className="px-4 py-2 bg-slate-800 flex items-center justify-between text-[11px]">
                <div className="flex items-center space-x-1.5">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="p-1 rounded bg-slate-700 disabled:opacity-40"
                    title="Previous page"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </button>
                  <span>
                    Page {page} of {totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="p-1 rounded bg-slate-700 disabled:opacity-40"
                    title="Next page"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="flex items-center space-x-1.5">
                  <button
                    type="button"
                    onClick={() => setZoom((z) => Math.max(60, z - 20))}
                    className="p-1 rounded bg-slate-700"
                    title="Zoom out"
                  >
                    <ZoomOut className="w-3.5 h-3.5" />
                  </button>
                  <span className="w-10 text-center font-mono">{zoom}%</span>
                  <button
                    type="button"
                    onClick={() => setZoom((z) => Math.min(200, z + 20))}
                    className="p-1 rounded bg-slate-700"
                    title="Zoom in"
                  >
                    <ZoomIn className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRawText((v) => !v)}
                    className={`px-2 py-1 rounded text-[10px] font-semibold ${
                      showRawText ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-200'
                    }`}
                  >
                    {showRawText ? 'Show Image/PDF' : 'Raw OCR Text'}
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-auto p-4 flex items-start justify-center">
                {showRawText ? (
                  <pre className="w-full text-[11px] font-mono bg-slate-950 p-4 rounded-xl border border-slate-700 whitespace-pre-wrap text-slate-200">
                    {doc?.extraction?.raw_text || 'No raw OCR text available yet.'}
                  </pre>
                ) : previewUrl ? (
                  <img
                    src={previewUrl}
                    alt={doc?.original_filename || 'Document preview'}
                    style={{ width: `${zoom}%` }}
                    className="max-w-none rounded shadow-lg bg-white"
                  />
                ) : (
                  <div className="text-slate-400 text-center py-12">
                    Document preview loading or unavailable.
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT PANEL: Extracted Data, Validation, Edits & Confirmation */}
            <div className="overflow-y-auto p-5 space-y-4 bg-white">
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}
              {banner && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>{banner}</span>
                </div>
              )}

              {/* Validation Errors & Warnings (Never Hidden) */}
              {((doc?.extraction?.validation_errors?.length || 0) > 0 ||
                (doc?.extraction?.validation_warnings?.length || 0) > 0) && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-1">
                  <div className="font-bold text-amber-900 flex items-center space-x-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    <span>Validation Alerts (Review Carefully Before Confirming)</span>
                  </div>
                  {doc?.extraction?.validation_errors.map((e, i) => (
                    <div key={`ve-${i}`} className="text-rose-700 font-medium">
                      • Error: {e}
                    </div>
                  ))}
                  {doc?.extraction?.validation_warnings.map((w, i) => (
                    <div key={`vw-${i}`} className="text-amber-800">
                      • Warning: {w}
                    </div>
                  ))}
                </div>
              )}

              {/* Invoice Metadata */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="font-semibold text-gray-700">Merchant / Business</label>
                    {confBadge('merchant_name')}
                  </div>
                  <input
                    type="text"
                    placeholder="Merchant Name"
                    value={merchantName}
                    onChange={(e) => setMerchantName(e.target.value)}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="font-semibold text-gray-700">Invoice / Bill Number</label>
                    {confBadge('invoice_number')}
                  </div>
                  <input
                    type="text"
                    placeholder="Invoice Number"
                    value={invoiceNumber}
                    onChange={(e) => setInvoiceNumber(e.target.value)}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="font-semibold text-gray-700">Invoice Date</label>
                    {confBadge('invoice_date')}
                  </div>
                  <input
                    type="date"
                    aria-label="Invoice Date"
                    value={invoiceDate}
                    onChange={(e) => setInvoiceDate(e.target.value)}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="font-semibold text-gray-700">Due Date</label>
                    {confBadge('due_date')}
                  </div>
                  <input
                    type="date"
                    aria-label="Due Date"
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg"
                  />
                </div>
              </div>

              {/* Financial Amounts & Indian GST */}
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2.5">
                <div className="font-bold text-gray-800">Financial Amounts &amp; Indian GST</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  <div>
                    <div className="flex justify-between mb-1">
                      <label className="text-gray-600 font-medium">Grand Total</label>
                      {confBadge('grand_total')}
                    </div>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Missing"
                      value={grandTotal}
                      onChange={(e) => setGrandTotal(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg font-mono font-bold bg-white"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <label className="text-gray-600 font-medium">Subtotal</label>
                      {confBadge('subtotal')}
                    </div>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Missing"
                      value={subtotal}
                      onChange={(e) => setSubtotal(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg font-mono bg-white"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <label className="text-gray-600 font-medium">Total Tax</label>
                      {confBadge('total_tax')}
                    </div>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Missing"
                      value={totalTax}
                      onChange={(e) => setTotalTax(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg font-mono bg-white"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <label className="text-gray-600 font-medium">GSTIN</label>
                      {confBadge('gstin')}
                    </div>
                    <input
                      type="text"
                      placeholder="29ABCDE1234F1Z5"
                      value={gstin}
                      onChange={(e) => setGstin(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg font-mono bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-600 font-medium mb-1">CGST / SGST</label>
                    <div className="grid grid-cols-2 gap-1">
                      <input
                        type="number"
                        step="0.01"
                        placeholder="CGST"
                        value={cgst}
                        onChange={(e) => setCgst(e.target.value)}
                        className="px-2 py-1.5 border border-gray-300 rounded font-mono bg-white"
                      />
                      <input
                        type="number"
                        step="0.01"
                        placeholder="SGST"
                        value={sgst}
                        onChange={(e) => setSgst(e.target.value)}
                        className="px-2 py-1.5 border border-gray-300 rounded font-mono bg-white"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-gray-600 font-medium mb-1">IGST / Currency</label>
                    <div className="grid grid-cols-2 gap-1">
                      <input
                        type="number"
                        step="0.01"
                        placeholder="IGST"
                        value={igst}
                        onChange={(e) => setIgst(e.target.value)}
                        className="px-2 py-1.5 border border-gray-300 rounded font-mono bg-white"
                      />
                      <input
                        type="text"
                        value={currency}
                        onChange={(e) => setCurrency(e.target.value)}
                        className="px-2 py-1.5 border border-gray-300 rounded bg-white"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Line Items */}
              <div className="border border-gray-200 rounded-xl p-3 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-gray-800">
                    Line Items ({lineItems.length})
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      setLineItems((p) => [
                        ...p,
                        { description: '', quantity: '1', unit_price: '', total: '' },
                      ])
                    }
                    className="text-blue-600 hover:underline inline-flex items-center space-x-1"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Add Item</span>
                  </button>
                </div>
                {lineItems.map((it, idx) => (
                  <div key={idx} className="grid grid-cols-12 gap-1.5 items-center">
                    <input
                      type="text"
                      placeholder="Description"
                      value={it.description}
                      onChange={(e) => {
                        const val = e.target.value;
                        setLineItems((prev) =>
                          prev.map((row, rIdx) => (rIdx === idx ? { ...row, description: val } : row))
                        );
                      }}
                      className="col-span-6 px-2 py-1 border border-gray-300 rounded"
                    />
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Qty"
                      value={it.quantity ?? ''}
                      onChange={(e) => {
                        const val = e.target.value;
                        setLineItems((prev) =>
                          prev.map((row, rIdx) => (rIdx === idx ? { ...row, quantity: val } : row))
                        );
                      }}
                      className="col-span-2 px-2 py-1 border border-gray-300 rounded font-mono"
                    />
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Total"
                      value={it.total ?? ''}
                      onChange={(e) => {
                        const val = e.target.value;
                        setLineItems((prev) =>
                          prev.map((row, rIdx) => (rIdx === idx ? { ...row, total: val } : row))
                        );
                      }}
                      className="col-span-3 px-2 py-1 border border-gray-300 rounded font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setLineItems((prev) => prev.filter((_, rIdx) => rIdx !== idx))}
                      className="col-span-1 text-rose-500 hover:text-rose-700 flex justify-center"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>

              {/* Save Edits / Confirmation Action Bar */}
              <div className="p-3.5 bg-indigo-50/50 border border-indigo-200 rounded-xl space-y-3">
                <div className="font-bold text-indigo-950 flex items-center space-x-1.5">
                  <Link2 className="w-4 h-4 text-indigo-600" />
                  <span>Confirm Document &amp; Choose Financial Record Action</span>
                </div>
                <select
                  aria-label="Confirmation Action"
                  value={confirmAction}
                  onChange={(e) => setConfirmAction(e.target.value as typeof confirmAction)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white font-medium"
                >
                  <option value="standalone">Confirm as Standalone Document</option>
                  <option value="create_bill">Create New Unpaid Bill (Human Confirmed)</option>
                  <option value="create_transaction">
                    Create Ledger Transaction (Human Confirmed)
                  </option>
                  <option value="link_bill">Link to Existing Bill</option>
                  <option value="link_transaction">Link to Existing Transaction</option>
                  <option value="link_subscription">Link to Existing Subscription</option>
                  <option value="link_loan">Link to Existing Loan</option>
                </select>

                {(confirmAction === 'create_transaction' || confirmAction === 'create_bill') && (
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      {confirmAction === 'create_transaction'
                        ? 'Payment Account *'
                        : 'Optional Linked Payment Account'}
                    </label>
                    <select
                      value={selectedAccountId}
                      onChange={(e) => setSelectedAccountId(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
                    >
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name} ({formatINR(a.current_balance)})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {confirmAction.startsWith('link_') && (
                  <select
                    value={targetId}
                    onChange={(e) => setTargetId(e.target.value)}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white"
                  >
                    <option value="">-- Select target record --</option>
                    {confirmAction === 'link_bill' &&
                      bills.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.bill_name} (Due {formatDate(b.due_date)})
                        </option>
                      ))}
                    {confirmAction === 'link_transaction' &&
                      transactions.map((t) => (
                        <option key={t.id} value={t.id}>
                          {formatDate(t.transaction_date)} — {t.description} ({formatINR(t.amount)})
                        </option>
                      ))}
                    {confirmAction === 'link_subscription' &&
                      subscriptions.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.subscription_name} ({s.status})
                        </option>
                      ))}
                    {confirmAction === 'link_loan' &&
                      loans.map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.loan_name} (EMI {formatINR(l.emi_amount)})
                        </option>
                      ))}
                  </select>
                )}

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={handleSaveEdits}
                    className="px-3 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-800 rounded-lg font-semibold inline-flex items-center space-x-1"
                  >
                    <Save className="w-3.5 h-3.5" />
                    <span>Save Edits</span>
                  </button>
                  <button
                    type="button"
                    disabled={busy || doc?.processing_status === 'rejected'}
                    onClick={handleConfirm}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg font-semibold inline-flex items-center space-x-1"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Confirm Document</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRejectBox((v) => !v)}
                    className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg font-semibold inline-flex items-center space-x-1"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    <span>Reject</span>
                  </button>
                </div>

                {showRejectBox && (
                  <div className="pt-2 flex gap-2">
                    <input
                      type="text"
                      placeholder="Rejection reason (e.g. blurred / unrelated document)"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      className="flex-1 px-2.5 py-1.5 border border-rose-300 rounded-lg bg-white"
                    />
                    <button
                      type="button"
                      disabled={busy || rejectReason.trim().length < 2}
                      onClick={handleReject}
                      className="px-3 py-1.5 bg-rose-600 text-white rounded-lg font-semibold disabled:opacity-50"
                    >
                      Submit Rejection
                    </button>
                  </div>
                )}
              </div>

              {/* Linked Records & Audit History */}
              {(doc?.links?.length || 0) > 0 && (
                <div className="border border-gray-200 rounded-xl p-3 space-y-1">
                  <div className="font-bold text-gray-800">Linked Financial Records</div>
                  {doc?.links.map((lk) => (
                    <div key={lk.id} className="text-[11px] text-gray-600">
                      • <strong className="uppercase">{lk.target_type}</strong>:{' '}
                      {lk.target_label || lk.bill_id || lk.transaction_id || lk.subscription_id || lk.loan_id}{' '}
                      ({lk.link_role})
                    </div>
                  ))}
                </div>
              )}

              {(doc?.review_events?.length || 0) > 0 && (
                <div className="border border-gray-200 rounded-xl p-3 space-y-1">
                  <div className="font-bold text-gray-800">Review &amp; Audit History</div>
                  {doc?.review_events.slice(0, 8).map((ev) => (
                    <div key={ev.id} className="flex justify-between text-[11px] text-gray-500">
                      <span className="capitalize font-medium">{ev.action.replace('_', ' ')}</span>
                      <span>{new Date(ev.created_at).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
