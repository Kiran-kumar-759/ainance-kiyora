import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Download,
  FileText,
  Printer,
  RefreshCw,
} from 'lucide-react';
import { analyticsApi } from '../../services/analyticsApi';
import { financeApi } from '../../services/financeApi';
import { FinancialAccount, FinancialCategory } from '../../types/finance';
import {
  FinancialReportResponse,
  ReportDefinition,
  ReportType,
} from '../../types/analytics';
import { formatDate, formatINR } from '../../lib/formatters';
import { DASHBOARD_PERIOD_OPTIONS } from '../../components/analytics/PeriodFilterBar';
import { WorkspaceStarterBanner } from '../../components/finance/WorkspaceStarterBanner';

interface ReportsPageProps {
  onNavigate: (view: string) => void;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ onNavigate }) => {
  const [definitions, setDefinitions] = useState<ReportDefinition[]>([]);
  const [reportType, setReportType] = useState<ReportType>('monthly_summary');
  const [period, setPeriod] = useState<string>('this_month');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [accountId, setAccountId] = useState<string>('');
  const [txType, setTxType] = useState<string>('');
  const [categoryId, setCategoryId] = useState<string>('');
  const [source, setSource] = useState<string>('');

  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [categories, setCategories] = useState<FinancialCategory[]>([]);
  const [report, setReport] = useState<FinancialReportResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      analyticsApi.listReports(),
      financeApi.listAccounts(false),
      financeApi.listCategories(),
    ])
      .then(([defs, accs, cats]) => {
        setDefinitions(defs.reports);
        setAccounts(accs);
        setCategories(cats);
      })
      .catch(() => {});
  }, []);

  const loadReport = async () => {
    if (period === 'custom') {
      if (!startDate || !endDate) {
        setError('Please select both Start Date and End Date for a custom report.');
        return;
      }
      if (startDate > endDate) {
        setError('Start Date cannot be after End Date.');
        return;
      }
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await analyticsApi.getReport(reportType, {
        period,
        start_date: period === 'custom' ? startDate : undefined,
        end_date: period === 'custom' ? endDate : undefined,
        account_id: accountId || undefined,
        transaction_type: txType || undefined,
        category_id: categoryId || undefined,
        source: source || undefined,
      });
      setReport(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate financial report.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (period !== 'custom') {
      loadReport();
    }
  }, [reportType, period, accountId, txType, categoryId, source]);

  const handleExportCsv = async () => {
    if (isExporting) return;
    setIsExporting(true);
    setError(null);
    try {
      const { filename, content } = await analyticsApi.exportReportCsv(reportType, {
        period,
        start_date: period === 'custom' ? startDate : undefined,
        end_date: period === 'custom' ? endDate : undefined,
        account_id: accountId || undefined,
        transaction_type: txType || undefined,
        category_id: categoryId || undefined,
        source: source || undefined,
      });
      const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'CSV export failed.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Heading & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
            <FileText className="w-6 h-6 text-indigo-600" />
            <span>Financial Reports &amp; Exports</span>
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Generate auditable summaries, filter ledger transactions, print statements, and export CSVs.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-semibold rounded-lg shadow-sm"
          >
            <Printer className="w-4 h-4" />
            <span>Print Report</span>
          </button>

          <button
            type="button"
            disabled={isExporting || isLoading}
            onClick={handleExportCsv}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm"
          >
            {isExporting ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-4 print:hidden">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
          <div>
            <label className="block font-semibold text-gray-700 mb-1">Report Type</label>
            <select
              aria-label="Report Type"
              value={reportType}
              onChange={(e) => setReportType(e.target.value as ReportType)}
              className="w-full px-2.5 py-2 border border-gray-300 rounded-lg bg-white"
            >
              {(definitions.length > 0
                ? definitions
                : [
                    { id: 'monthly_summary', title: 'Monthly Financial Summary' },
                    { id: 'income_report', title: 'Income Report' },
                    { id: 'expense_report', title: 'Expense Report' },
                    { id: 'category_spending', title: 'Category-Wise Spending Report' },
                    { id: 'account_activity', title: 'Account-Wise Activity Report' },
                    { id: 'cash_flow', title: 'Cash-Flow Report' },
                    { id: 'savings_report', title: 'Savings Report' },
                    { id: 'transaction_summary', title: 'Transaction Summary Report' },
                  ]
              ).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">Period</label>
            <select
              aria-label="Report Period"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="w-full px-2.5 py-2 border border-gray-300 rounded-lg bg-white"
            >
              {DASHBOARD_PERIOD_OPTIONS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">Account</label>
            <select
              aria-label="Report Account"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="w-full px-2.5 py-2 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">Transaction Type</label>
            <select
              aria-label="Report Transaction Type"
              value={txType}
              onChange={(e) => setTxType(e.target.value)}
              className="w-full px-2.5 py-2 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">Default / All</option>
              <option value="income">Income</option>
              <option value="expense">Expense</option>
              <option value="transfer">Transfer</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">Category</label>
            <select
              aria-label="Report Category"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="w-full px-2.5 py-2 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold text-gray-700 mb-1">Source</label>
            <select
              aria-label="Report Source"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full px-2.5 py-2 border border-gray-300 rounded-lg bg-white"
            >
              <option value="">All Sources</option>
              <option value="manual">Manual</option>
              <option value="csv_import">CSV Import</option>
              <option value="xlsx_import">XLSX Import</option>
              <option value="demo_bank">Demo Bank</option>
            </select>
          </div>
        </div>

        {period === 'custom' && (
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-gray-100 text-xs">
            <div>
              <label className="mr-2 font-semibold text-gray-700">Start Date:</label>
              <input
                type="date"
                aria-label="Report Start Date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="mr-2 font-semibold text-gray-700">End Date:</label>
              <input
                type="date"
                aria-label="Report End Date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded-lg"
              />
            </div>
            <button
              type="button"
              onClick={loadReport}
              className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg"
            >
              Generate Report
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-center space-x-2">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={loadReport} className="underline font-medium">
            Retry
          </button>
        </div>
      )}

      {!isLoading && accounts.length === 0 && (
        <WorkspaceStarterBanner
          title="No accounts or statements recorded yet"
          description="Connect a bank account, add a manual account, or upload a CSV/XLSX statement so your financial reports and CSV exports reflect real ledger entries."
          onNavigate={onNavigate}
        />
      )}

      {/* Printable Report Sheet */}
      {isLoading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-10 text-center text-gray-500 text-sm">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
          Generating PostgreSQL-backed financial report...
        </div>
      ) : (
        report && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-6 print:shadow-none print:border-0">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between pb-4 border-b border-gray-200 gap-2">
              <div>
                <h2 className="text-xl font-bold text-gray-900">{report.metadata.title}</h2>
                <p className="text-xs text-gray-600 mt-1">
                  Period:{' '}
                  <strong>
                    {formatDate(report.metadata.start_date)} to{' '}
                    {formatDate(report.metadata.end_date)}
                  </strong>{' '}
                  • Currency: <strong>{report.metadata.currency}</strong> ({report.metadata.timezone})
                </p>
              </div>
              <div className="text-right text-[11px] text-gray-500">
                <div>Generated: {formatDate(report.metadata.generated_at)}</div>
                <div>{report.total_transactions} matching records</div>
              </div>
            </div>

            {/* Summary Metrics */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {report.summary_metrics.map((m) => (
                <div key={m.label} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-[11px] font-semibold uppercase text-gray-500">{m.label}</div>
                  <div
                    className={`text-lg font-bold mt-1 ${
                      m.highlight === 'positive'
                        ? 'text-emerald-700'
                        : m.highlight === 'negative'
                          ? 'text-rose-700'
                          : 'text-gray-900'
                    }`}
                  >
                    {m.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Category & Account Breakdowns */}
            {(report.category_breakdown.length > 0 || report.account_breakdown.length > 0) && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {report.category_breakdown.length > 0 && (
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700 mb-2">
                      Category Breakdown
                    </h3>
                    <table className="w-full text-left text-xs border border-gray-200 rounded-lg overflow-hidden">
                      <thead className="bg-gray-50 text-gray-600 border-b border-gray-200">
                        <tr>
                          <th className="py-2 px-3">Category</th>
                          <th className="py-2 px-3 text-right">Txns</th>
                          <th className="py-2 px-3 text-right">Share</th>
                          <th className="py-2 px-3 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {report.category_breakdown.map((c, idx) => (
                          <tr key={`${c.category_id || 'u'}-${idx}`}>
                            <td className="py-2 px-3 font-medium text-gray-800">
                              {c.category_name}
                            </td>
                            <td className="py-2 px-3 text-right text-gray-500">
                              {c.transaction_count}
                            </td>
                            <td className="py-2 px-3 text-right text-gray-600">{c.percentage}%</td>
                            <td className="py-2 px-3 text-right font-bold text-gray-900">
                              {formatINR(c.total_amount)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {report.account_breakdown.length > 0 && (
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700 mb-2">
                      Account Breakdown
                    </h3>
                    <table className="w-full text-left text-xs border border-gray-200 rounded-lg overflow-hidden">
                      <thead className="bg-gray-50 text-gray-600 border-b border-gray-200">
                        <tr>
                          <th className="py-2 px-3">Account</th>
                          <th className="py-2 px-3 text-right">Txns</th>
                          <th className="py-2 px-3 text-right">Share</th>
                          <th className="py-2 px-3 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {report.account_breakdown.map((a) => (
                          <tr key={a.account_id}>
                            <td className="py-2 px-3 font-medium text-gray-800">
                              {a.account_name}
                            </td>
                            <td className="py-2 px-3 text-right text-gray-500">
                              {a.transaction_count}
                            </td>
                            <td className="py-2 px-3 text-right text-gray-600">{a.percentage}%</td>
                            <td className="py-2 px-3 text-right font-bold text-gray-900">
                              {formatINR(a.total_amount)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Detailed Transactions Table */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700 mb-2">
                Transaction Ledger Details ({report.transactions.length})
              </h3>
              {report.transactions.length === 0 ? (
                <div className="p-6 text-center text-xs text-gray-500 border border-dashed border-gray-200 rounded-xl">
                  No transactions match the selected report filters.
                </div>
              ) : (
                <div className="overflow-x-auto border border-gray-200 rounded-xl">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-600">
                      <tr>
                        <th className="py-2 px-3">Date</th>
                        <th className="py-2 px-3">Description</th>
                        <th className="py-2 px-3">Category</th>
                        <th className="py-2 px-3">Account</th>
                        <th className="py-2 px-3">Type</th>
                        <th className="py-2 px-3">Source</th>
                        <th className="py-2 px-3 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {report.transactions.map((tx) => (
                        <tr key={tx.id}>
                          <td className="py-2 px-3 whitespace-nowrap text-gray-500">
                            {formatDate(tx.transaction_date)}
                          </td>
                          <td className="py-2 px-3 font-medium text-gray-900">{tx.description}</td>
                          <td className="py-2 px-3">{tx.category_name || 'Uncategorized'}</td>
                          <td className="py-2 px-3 text-gray-600">{tx.account_name}</td>
                          <td className="py-2 px-3 uppercase font-semibold text-[10px]">
                            {tx.transaction_type}
                          </td>
                          <td className="py-2 px-3 uppercase text-[10px] text-gray-500">
                            {tx.source}
                          </td>
                          <td
                            className={`py-2 px-3 text-right font-bold whitespace-nowrap ${
                              tx.transaction_type === 'income'
                                ? 'text-emerald-700'
                                : tx.transaction_type === 'expense'
                                  ? 'text-rose-700'
                                  : 'text-blue-700'
                            }`}
                          >
                            {formatINR(tx.amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="text-[11px] text-gray-500 pt-2 border-t border-gray-100">
              Audit Note: {report.traceability.formula} • Included:{' '}
              {report.traceability.included_transaction_count} • Excluded transfers:{' '}
              {report.traceability.excluded_transfer_count} • Excluded reversed journals:{' '}
              {report.traceability.excluded_reversed_count}
            </div>
          </div>
        )
      )}
    </div>
  );
};
