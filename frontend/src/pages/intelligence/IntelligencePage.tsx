import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  Check,
  CheckCircle2,
  Clock,
  Cpu,
  Edit3,
  Lightbulb,
  Play,
  PlusCircle,
  RefreshCw,
  Repeat,
  Search,
  Sparkles,
  Store,
  Tag,
  X,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import { intelligenceApi } from '../../services/intelligenceApi';
import { FinancialCategory } from '../../types/finance';
import {
  CategorizationFeedbackItem,
  FinancialInsightList,
  IntelligenceOverview,
  MerchantIdentityItem,
  MerchantList,
  RecurringCandidateList,
  SpendingAnomalyList,
  SpendingPatterns,
  TransactionCategorization,
  TransactionCategorizationList,
} from '../../types/intelligence';
import { formatDate, formatINR } from '../../lib/formatters';

interface IntelligencePageProps {
  onNavigate: (view: string) => void;
}

type IntelTab =
  | 'overview'
  | 'categorization'
  | 'merchants'
  | 'recurring'
  | 'patterns'
  | 'anomalies'
  | 'insights';

const METHOD_BADGE: Record<string, string> = {
  user_override: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  user_confirmed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  confirmed_mapping: 'bg-teal-50 text-teal-700 border-teal-200',
  deterministic_rule: 'bg-sky-50 text-sky-700 border-sky-200',
  ml_classifier: 'bg-violet-50 text-violet-700 border-violet-200',
  llm_fallback: 'bg-amber-50 text-amber-700 border-amber-200',
  existing_category: 'bg-slate-100 text-slate-700 border-slate-200',
  fallback: 'bg-rose-50 text-rose-700 border-rose-200',
};

const SEVERITY_BADGE: Record<string, string> = {
  high: 'bg-rose-50 text-rose-700 border-rose-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-sky-50 text-sky-700 border-sky-200',
  info: 'bg-slate-100 text-slate-700 border-slate-200',
};

export const IntelligencePage: React.FC<IntelligencePageProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<IntelTab>('overview');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [banner, setBanner] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [overview, setOverview] = useState<IntelligenceOverview | null>(null);
  const [categories, setCategories] = useState<FinancialCategory[]>([]);

  // Categorization state
  const [catData, setCatData] = useState<TransactionCategorizationList | null>(null);
  const [catStatusFilter, setCatStatusFilter] = useState('');
  const [catSearch, setCatSearch] = useState('');
  const [catPage, setCatPage] = useState(1);
  const [feedbackList, setFeedbackList] = useState<CategorizationFeedbackItem[]>([]);
  const [editingTx, setEditingTx] = useState<TransactionCategorization | null>(null);
  const [overrideCategoryId, setOverrideCategoryId] = useState('');
  const [overrideMerchantName, setOverrideMerchantName] = useState('');
  const [overrideNotes, setOverrideNotes] = useState('');
  const [saveMerchantMapping, setSaveMerchantMapping] = useState(true);

  // Merchants state
  const [merchantData, setMerchantData] = useState<MerchantList | null>(null);
  const [merchantSearch, setMerchantSearch] = useState('');
  const [editingMerchant, setEditingMerchant] = useState<MerchantIdentityItem | null>(null);
  const [editMerchName, setEditMerchName] = useState('');
  const [editMerchCatId, setEditMerchCatId] = useState('');

  // Recurring state
  const [recurringData, setRecurringData] = useState<RecurringCandidateList | null>(null);
  const [recurringFilter, setRecurringFilter] = useState('');

  // Patterns state
  const [patternsData, setPatternsData] = useState<SpendingPatterns | null>(null);
  const [patternFrom, setPatternFrom] = useState('');
  const [patternTo, setPatternTo] = useState('');

  // Anomalies state
  const [anomaliesData, setAnomaliesData] = useState<SpendingAnomalyList | null>(null);
  const [anomalyFilter, setAnomalyFilter] = useState('');

  // Insights state
  const [insightsData, setInsightsData] = useState<FinancialInsightList | null>(null);
  const [insightFilter, setInsightFilter] = useState('');

  const loadCore = async () => {
    setLoading(true);
    try {
      const [ov, cats] = await Promise.all([
        intelligenceApi.getOverview(),
        financeApi.listCategories().catch(() => []),
      ]);
      setOverview(ov);
      setCategories(cats);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  const loadTab = async (tab: IntelTab) => {
    try {
      if (tab === 'overview') {
        const ov = await intelligenceApi.getOverview();
        setOverview(ov);
      } else if (tab === 'categorization') {
        const [cats, fb] = await Promise.all([
          intelligenceApi.listCategorizations({
            review_status: catStatusFilter || undefined,
            search: catSearch || undefined,
            page: catPage,
            page_size: 20,
          }),
          intelligenceApi.listFeedback(),
        ]);
        setCatData(cats);
        setFeedbackList(fb);
      } else if (tab === 'merchants') {
        const res = await intelligenceApi.listMerchants({
          search: merchantSearch || undefined,
          page: 1,
          page_size: 50,
        });
        setMerchantData(res);
      } else if (tab === 'recurring') {
        const res = await intelligenceApi.listRecurringCandidates(recurringFilter || undefined);
        setRecurringData(res);
      } else if (tab === 'patterns') {
        const res = await intelligenceApi.getSpendingPatterns({
          date_from: patternFrom || undefined,
          date_to: patternTo || undefined,
        });
        setPatternsData(res);
      } else if (tab === 'anomalies') {
        const res = await intelligenceApi.listAnomalies({
          review_status: anomalyFilter || undefined,
        });
        setAnomaliesData(res);
      } else if (tab === 'insights') {
        const res = await intelligenceApi.listInsights(insightFilter || undefined);
        setInsightsData(res);
      }
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  useEffect(() => {
    loadCore();
  }, []);

  useEffect(() => {
    loadTab(activeTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, catStatusFilter, catPage, recurringFilter, anomalyFilter, insightFilter]);

  const handleRunPipeline = async (reanalyzeAll = false, asyncJob = false) => {
    setRunning(true);
    setBanner(null);
    try {
      const job = await intelligenceApi.runFullPipeline({
        reanalyze_all: reanalyzeAll,
        use_ai_fallback: true,
        train_model: true,
        async_job: asyncJob,
      });
      setBanner({
        type: 'success',
        text: asyncJob
          ? `Background AI analysis job queued (Job ID: ${job.id.slice(0, 8)}).`
          : `Intelligence analysis completed: ${job.items_processed} transaction(s) analyzed.`,
      });
      await Promise.all([loadCore(), loadTab(activeTab)]);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    } finally {
      setRunning(false);
    }
  };

  const handleTrainModel = async () => {
    setRunning(true);
    setBanner(null);
    try {
      const meta = await intelligenceApi.trainMlModel();
      setBanner({
        type: 'success',
        text:
          meta.status === 'trained'
            ? `Personal ML classifier trained on ${meta.training_sample_count} samples across ${meta.class_count} categories.`
            : meta.evaluation_notes || 'Insufficient labeled data for ML training.',
      });
      await loadCore();
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    } finally {
      setRunning(false);
    }
  };

  const handleConfirmSuggestion = async (item: TransactionCategorization) => {
    const targetCatId = item.suggested_category_id || item.current_category_id;
    if (!targetCatId) {
      setBanner({ type: 'error', text: 'Select a category via Override before confirming.' });
      return;
    }
    try {
      await intelligenceApi.overrideCategorization(item.transaction_id, {
        category_id: targetCatId,
        save_merchant_mapping: true,
        action: 'confirm',
      });
      setBanner({ type: 'success', text: 'Confirmed transaction category and saved learning feedback.' });
      await Promise.all([loadTab('categorization'), loadCore()]);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  const handleSubmitOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTx || !overrideCategoryId) return;
    try {
      await intelligenceApi.overrideCategorization(editingTx.transaction_id, {
        category_id: overrideCategoryId,
        normalized_merchant_name: overrideMerchantName.trim() || undefined,
        save_merchant_mapping: saveMerchantMapping,
        action: 'override',
        notes: overrideNotes.trim() || undefined,
      });
      setEditingTx(null);
      setBanner({ type: 'success', text: 'Category overridden and user preference saved.' });
      await Promise.all([loadTab('categorization'), loadCore()]);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  const handleSaveMerchant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingMerchant) return;
    try {
      await intelligenceApi.updateMerchant(editingMerchant.id, {
        normalized_name: editMerchName.trim() || undefined,
        default_category_id: editMerchCatId || undefined,
        is_user_confirmed: true,
        apply_to_existing_transactions: true,
      });
      setEditingMerchant(null);
      setBanner({ type: 'success', text: 'Merchant normalization and default category updated.' });
      await Promise.all([loadTab('merchants'), loadCore()]);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  const handleRecurringAction = async (
    candidateId: string,
    decision: 'confirm' | 'reject',
    createSubscription = false
  ) => {
    try {
      await intelligenceApi.decideRecurringCandidate(candidateId, {
        decision,
        create_subscription: createSubscription,
      });
      setBanner({
        type: 'success',
        text: createSubscription
          ? 'Recurring candidate confirmed and added to Subscriptions.'
          : `Recurring candidate marked as ${decision === 'confirm' ? 'confirmed' : 'rejected'}.`,
      });
      await Promise.all([loadTab('recurring'), loadCore()]);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  const handleAnomalyAction = async (id: string, action: 'acknowledge' | 'dismiss' | 'reopen') => {
    try {
      await intelligenceApi.reviewAnomaly(id, action);
      await Promise.all([loadTab('anomalies'), loadCore()]);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  const handleInsightAction = async (id: string, action: 'mark_read' | 'dismiss' | 'reopen') => {
    try {
      await intelligenceApi.reviewInsight(id, action);
      await Promise.all([loadTab('insights'), loadCore()]);
    } catch (err) {
      setBanner({ type: 'error', text: (err as Error).message });
    }
  };

  const metrics = overview?.metrics;

  const tabs: { id: IntelTab; label: string; icon: React.ComponentType<{ className?: string }>; badge?: number }[] = [
    { id: 'overview', label: 'Overview', icon: Sparkles },
    {
      id: 'categorization',
      label: 'Transaction Intelligence',
      icon: Tag,
      badge: metrics?.needs_review_count,
    },
    { id: 'merchants', label: 'Merchants', icon: Store, badge: metrics?.merchant_count },
    {
      id: 'recurring',
      label: 'Recurring Payments',
      icon: Repeat,
      badge: metrics?.pending_recurring_count,
    },
    { id: 'patterns', label: 'Spending Patterns', icon: BarChart3 },
    {
      id: 'anomalies',
      label: 'Anomalies',
      icon: AlertTriangle,
      badge: metrics?.open_anomaly_count,
    },
    {
      id: 'insights',
      label: 'AI Insights',
      icon: Lightbulb,
      badge: metrics?.unread_insight_count,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-indigo-600" />
            <span>AI Expense Intelligence</span>
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Explainable categorization, merchant normalization, personal TF-IDF classifier, recurring
            detection, statistical anomalies, and evidence-backed insights.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={running}
            onClick={() => handleRunPipeline(false, false)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-60 shadow-xs"
          >
            {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            <span>{running ? 'Analyzing...' : 'Run Full Analysis'}</span>
          </button>
          <button
            type="button"
            disabled={running}
            onClick={handleTrainModel}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50 disabled:opacity-60"
          >
            <Cpu className="w-4 h-4 text-violet-600" />
            <span>Train Personal ML</span>
          </button>
          <button
            type="button"
            disabled={running}
            onClick={() => handleRunPipeline(true, false)}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50 disabled:opacity-60"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Re-analyze All</span>
          </button>
        </div>
      </div>

      {banner && (
        <div
          className={`px-4 py-3 rounded-lg border text-sm flex items-center justify-between ${
            banner.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          <span>{banner.text}</span>
          <button type="button" onClick={() => setBanner(null)} className="text-xs underline ml-4">
            Dismiss
          </button>
        </div>
      )}

      {/* Sub-navigation tabs */}
      <div className="border-b border-slate-200 overflow-x-auto">
        <nav className="flex space-x-2 min-w-max pb-px">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-2 px-3.5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  active
                    ? 'border-indigo-600 text-indigo-700'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
                {typeof tab.badge === 'number' && tab.badge > 0 && (
                  <span className="px-1.5 py-0.5 text-[11px] font-semibold rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {loading && !overview ? (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-500 text-sm">
          Loading AI Expense Intelligence...
        </div>
      ) : null}

      {/* 1. OVERVIEW TAB */}
      {activeTab === 'overview' && overview && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs font-medium text-slate-500 uppercase">Analyzed Coverage</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">
                {metrics?.total_analyzed_transactions ?? 0}{' '}
                <span className="text-sm font-normal text-slate-500">
                  / {metrics?.total_eligible_transactions ?? 0} txns
                </span>
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {metrics?.needs_review_count ?? 0} awaiting review • {metrics?.confirmed_count ?? 0} user confirmed
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs font-medium text-slate-500 uppercase">Personal ML Model</div>
              <div className="text-2xl font-bold text-slate-900 mt-1 capitalize">
                {metrics?.ml_model_status?.replace('_', ' ') ?? 'Untrained'}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {metrics?.ml_training_samples ?? 0} labeled samples • Groq:{' '}
                <span className={metrics?.groq_enabled ? 'text-emerald-600 font-medium' : 'text-slate-600'}>
                  {metrics?.groq_enabled ? `Enabled (${metrics.groq_model})` : 'Local Fallback Mode'}
                </span>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs font-medium text-slate-500 uppercase">Recurring & Merchants</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">
                {metrics?.merchant_count ?? 0}{' '}
                <span className="text-sm font-normal text-slate-500">merchants</span>
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {metrics?.recurring_candidate_count ?? 0} recurring detected ({metrics?.pending_recurring_count ?? 0} pending)
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs font-medium text-slate-500 uppercase">Anomalies & Insights</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">
                {metrics?.open_anomaly_count ?? 0}{' '}
                <span className="text-sm font-normal text-slate-500">open alerts</span>
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {metrics?.high_severity_anomaly_count ?? 0} high severity • {metrics?.unread_insight_count ?? 0} unread insights
              </div>
            </div>
          </div>

          {/* Model Metrics + Top Categories */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">Per-User ML Classifier Evaluation</h3>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono">
                  {overview.model_metadata?.model_name ?? 'tfidf_logreg_per_user'}
                </span>
              </div>
              {overview.model_metadata?.status === 'trained' ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                      <div className="text-[11px] text-slate-500">Accuracy</div>
                      <div className="text-base font-bold text-slate-900">
                        {overview.model_metadata.accuracy
                          ? `${(Number(overview.model_metadata.accuracy) * 100).toFixed(1)}%`
                          : 'N/A'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                      <div className="text-[11px] text-slate-500">Precision</div>
                      <div className="text-base font-bold text-slate-900">
                        {overview.model_metadata.precision_weighted
                          ? `${(Number(overview.model_metadata.precision_weighted) * 100).toFixed(1)}%`
                          : 'N/A'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                      <div className="text-[11px] text-slate-500">Recall</div>
                      <div className="text-base font-bold text-slate-900">
                        {overview.model_metadata.recall_weighted
                          ? `${(Number(overview.model_metadata.recall_weighted) * 100).toFixed(1)}%`
                          : 'N/A'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                      <div className="text-[11px] text-slate-500">F1 Score</div>
                      <div className="text-base font-bold text-slate-900">
                        {overview.model_metadata.f1_weighted
                          ? `${(Number(overview.model_metadata.f1_weighted) * 100).toFixed(1)}%`
                          : 'N/A'}
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-600">{overview.model_metadata.evaluation_notes}</p>
                </div>
              ) : (
                <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600">
                  {overview.model_metadata?.evaluation_notes ||
                    'Not trained yet. Click "Run Full Analysis" or confirm at least 12 labeled transactions across 2+ categories to train your personal TF-IDF classifier.'}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">Top Expense Categories (180d)</h3>
                <button
                  type="button"
                  onClick={() => setActiveTab('patterns')}
                  className="text-xs text-indigo-600 hover:underline font-medium"
                >
                  View Full Patterns →
                </button>
              </div>
              {overview.top_categories.length === 0 ? (
                <p className="text-sm text-slate-500">No expense transactions in range yet.</p>
              ) : (
                <div className="space-y-2.5">
                  {overview.top_categories.map((cat) => (
                    <div key={cat.category_name} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium text-slate-800">
                          {cat.category_name} ({cat.transaction_count})
                        </span>
                        <span className="text-slate-700 font-semibold">
                          {formatINR(cat.total_amount)} ({cat.share_pct}%)
                        </span>
                      </div>
                      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full"
                          style={{ width: `${Math.min(100, Number(cat.share_pct))}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Recent Jobs */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-900 mb-3">Recent Intelligence Processing Runs</h3>
            {overview.recent_jobs.length === 0 ? (
              <p className="text-sm text-slate-500">No intelligence runs recorded yet. Click "Run Full Analysis" to begin.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="py-2 pr-4">Job Type</th>
                      <th className="py-2 pr-4">Status</th>
                      <th className="py-2 pr-4">Provider / Model</th>
                      <th className="py-2 pr-4">Items</th>
                      <th className="py-2">Completed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {overview.recent_jobs.map((job) => (
                      <tr key={job.id}>
                        <td className="py-2 pr-4 font-medium text-slate-800">{job.job_type}</td>
                        <td className="py-2 pr-4">
                          <span className="px-2 py-0.5 text-xs rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {job.status}
                          </span>
                        </td>
                        <td className="py-2 pr-4 text-xs text-slate-600 font-mono">
                          {job.provider_name || 'local'} / {job.model_name || 'deterministic'}
                        </td>
                        <td className="py-2 pr-4">{job.items_processed}</td>
                        <td className="py-2 text-xs text-slate-500">
                          {job.completed_at ? formatDate(job.completed_at) : 'In progress'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. TRANSACTION INTELLIGENCE TAB */}
      {activeTab === 'categorization' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={catSearch}
                  onChange={(e) => setCatSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && loadTab('categorization')}
                  placeholder="Search description or category..."
                  className="pl-9 pr-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <select
                value={catStatusFilter}
                onChange={(e) => {
                  setCatPage(1);
                  setCatStatusFilter(e.target.value);
                }}
                className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg bg-white"
              >
                <option value="">All Statuses</option>
                <option value="needs_review">Needs Review</option>
                <option value="auto_categorized">Auto Categorized</option>
                <option value="confirmed">Confirmed</option>
                <option value="overridden">Overridden</option>
              </select>
              <button
                type="button"
                onClick={() => loadTab('categorization')}
                className="px-3 py-1.5 text-sm rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700"
              >
                Apply
              </button>
            </div>
            <div className="text-xs text-slate-500">
              {catData?.needs_review_count ?? 0} pending review • {catData?.confirmed_count ?? 0} confirmed
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Date & Description</th>
                  <th className="px-4 py-3">Normalized Merchant</th>
                  <th className="px-4 py-3">Amount</th>
                  <th className="px-4 py-3">Current → Suggested</th>
                  <th className="px-4 py-3">Method & Confidence</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {!catData || catData.items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                      No analyzed transactions match this filter. Click "Run Full Analysis" above to score transactions.
                    </td>
                  </tr>
                ) : (
                  catData.items.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">
                          {item.description || item.merchant_payee || 'Transaction'}
                        </div>
                        <div className="text-xs text-slate-500">
                          {formatDate(item.transaction_date)} • {item.transaction_type}
                        </div>
                        {item.explanation && (
                          <div className="text-xs text-slate-500 mt-0.5 max-w-md">{item.explanation}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-800">
                        {item.normalized_merchant_name || item.merchant_payee || '—'}
                      </td>
                      <td className="px-4 py-3 font-semibold text-slate-900 whitespace-nowrap">
                        {formatINR(item.amount)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-xs text-slate-500">
                          Current: {item.current_category_name || 'Uncategorized'}
                        </div>
                        <div className="font-medium text-indigo-700">
                          Suggested: {item.suggested_category_name || 'None'}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block px-2 py-0.5 text-[11px] font-medium rounded border ${
                            METHOD_BADGE[item.classification_method] || METHOD_BADGE.existing_category
                          }`}
                        >
                          {item.classification_method}
                        </span>
                        <div className="text-xs text-slate-500 mt-1">
                          {(Number(item.confidence) * 100).toFixed(0)}% confidence
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                          {item.review_status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap space-x-1.5">
                        {item.suggested_category_id && item.review_status !== 'confirmed' && (
                          <button
                            type="button"
                            onClick={() => handleConfirmSuggestion(item)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
                          >
                            <Check className="w-3.5 h-3.5" /> Confirm
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setEditingTx(item);
                            setOverrideCategoryId(
                              item.suggested_category_id || item.current_category_id || ''
                            );
                            setOverrideMerchantName(item.normalized_merchant_name || '');
                            setOverrideNotes('');
                          }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-white text-slate-700 border border-slate-200 hover:bg-slate-50"
                        >
                          <Edit3 className="w-3.5 h-3.5" /> Override
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {feedbackList.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-slate-900 mb-3">User Feedback Learning Audit</h3>
              <div className="space-y-2 text-xs">
                {feedbackList.slice(0, 8).map((fb) => (
                  <div
                    key={fb.id}
                    className="flex flex-wrap items-center justify-between py-2 border-b border-slate-100 last:border-0"
                  >
                    <div>
                      <span className="font-semibold uppercase text-indigo-700 mr-2">{fb.action}</span>
                      <span>
                        {fb.previous_category_name || 'Uncategorized'} →{' '}
                        <strong>{fb.new_category_name || 'Unchanged'}</strong>
                      </span>
                      {fb.new_merchant_name && (
                        <span className="text-slate-500 ml-2">({fb.new_merchant_name})</span>
                      )}
                    </div>
                    <span className="text-slate-400">{formatDate(fb.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 3. MERCHANTS TAB */}
      {activeTab === 'merchants' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-2">
            <Search className="w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={merchantSearch}
              onChange={(e) => setMerchantSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadTab('merchants')}
              placeholder="Search normalized merchant or category..."
              className="flex-1 text-sm focus:outline-none"
            />
            <button
              type="button"
              onClick={() => loadTab('merchants')}
              className="px-3 py-1.5 text-sm rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700"
            >
              Search
            </button>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Canonical Merchant</th>
                  <th className="px-4 py-3">Raw Statement Aliases</th>
                  <th className="px-4 py-3">Default Category</th>
                  <th className="px-4 py-3">Transactions</th>
                  <th className="px-4 py-3">Total Spent</th>
                  <th className="px-4 py-3 text-right">Edit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {!merchantData || merchantData.items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      No merchants normalized yet. Run Full Analysis first.
                    </td>
                  </tr>
                ) : (
                  merchantData.items.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                          <span>{m.normalized_name}</span>
                          {m.is_user_confirmed && (
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" aria-label="Confirmed" />
                          )}
                        </div>
                        <div className="text-xs text-slate-400 font-mono">{m.canonical_key}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600 max-w-xs">
                        {m.aliases.slice(0, 3).map((a) => (
                          <div key={a.id} className="truncate font-mono">
                            {a.raw_pattern} ({a.occurrence_count}×)
                          </div>
                        ))}
                      </td>
                      <td className="px-4 py-3 text-slate-700">{m.default_category_name || 'Unmapped'}</td>
                      <td className="px-4 py-3">{m.transaction_count}</td>
                      <td className="px-4 py-3 font-semibold">{formatINR(m.total_spent)}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingMerchant(m);
                            setEditMerchName(m.normalized_name);
                            setEditMerchCatId(m.default_category_id || '');
                          }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-slate-200 hover:bg-slate-50"
                        >
                          <Edit3 className="w-3.5 h-3.5" /> Edit
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. RECURRING PAYMENTS TAB */}
      {activeTab === 'recurring' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              {['', 'pending', 'confirmed', 'linked', 'rejected'].map((st) => (
                <button
                  key={st || 'all'}
                  type="button"
                  onClick={() => setRecurringFilter(st)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border ${
                    recurringFilter === st
                      ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                      : 'bg-white text-slate-600 border-slate-200'
                  }`}
                >
                  {st ? st.toUpperCase() : 'ALL'}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => onNavigate('subscriptions')}
              className="text-xs font-medium text-indigo-600 hover:underline"
            >
              Open Phase 6 Subscriptions →
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {!recurringData || recurringData.items.length === 0 ? (
              <div className="md:col-span-2 bg-white rounded-xl border border-slate-200 p-8 text-center text-sm text-slate-500">
                No recurring payment candidates detected for this filter.
              </div>
            ) : (
              recurringData.items.map((cand) => (
                <div key={cand.id} className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-slate-900">{cand.merchant_name}</h4>
                      <div className="text-xs text-slate-500 capitalize">
                        {cand.frequency.replace('_', ' ')} • {cand.commitment_type.replace('_', ' ')} •{' '}
                        {cand.suggested_category_name || 'Uncategorized'}
                      </div>
                    </div>
                    <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-slate-100 text-slate-700 capitalize">
                      {cand.review_status}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-xs bg-slate-50 p-2.5 rounded-lg">
                    <div>
                      <div className="text-slate-500">Typical Amount</div>
                      <div className="font-semibold text-slate-900">{formatINR(cand.estimated_amount)}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Range / Var</div>
                      <div className="font-medium text-slate-800">
                        {cand.is_variable_amount ? `Variable (±${cand.amount_variability_pct}%)` : 'Fixed'}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500">Next Expected</div>
                      <div className="font-medium text-slate-800">
                        {cand.next_expected_date ? formatDate(cand.next_expected_date) : '—'}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>
                      {cand.occurrence_count} charges • {(Number(cand.confidence) * 100).toFixed(0)}% confidence
                    </span>
                    <div className="flex items-center gap-2">
                      {cand.review_status === 'pending' && (
                        <>
                          <button
                            type="button"
                            onClick={() => handleRecurringAction(cand.id, 'confirm', false)}
                            className="px-2.5 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
                          >
                            Confirm
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRecurringAction(cand.id, 'confirm', true)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100"
                          >
                            <PlusCircle className="w-3.5 h-3.5" /> Add Subscription
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRecurringAction(cand.id, 'reject', false)}
                            className="px-2.5 py-1 rounded bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100"
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 5. SPENDING PATTERNS TAB */}
      {activeTab === 'patterns' && patternsData && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">From:</span>
              <input
                type="date"
                value={patternFrom}
                onChange={(e) => setPatternFrom(e.target.value)}
                className="border border-slate-200 rounded px-2 py-1"
              />
              <span className="text-slate-500">To:</span>
              <input
                type="date"
                value={patternTo}
                onChange={(e) => setPatternTo(e.target.value)}
                className="border border-slate-200 rounded px-2 py-1"
              />
              <button
                type="button"
                onClick={() => loadTab('patterns')}
                className="px-3 py-1 rounded bg-indigo-600 text-white font-medium"
              >
                Update Range
              </button>
            </div>
            <span className="text-xs text-slate-500 ml-auto">
              Window: {patternsData.period_start} to {patternsData.period_end}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Essential vs Discretionary</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {formatINR(patternsData.essential_total)}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                Discretionary: {formatINR(patternsData.discretionary_total)}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Fixed vs Variable</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {formatINR(patternsData.fixed_total)}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                Variable: {formatINR(patternsData.variable_total)}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Weekend Spend Share</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {patternsData.weekend_share_pct}%
              </div>
              <div className="text-xs text-slate-500 mt-1">
                Weekend: {formatINR(patternsData.weekend_expense)}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="text-xs text-slate-500 uppercase">Top 3 Merchant Share</div>
              <div className="text-lg font-bold text-slate-900 mt-1">
                {patternsData.top_3_merchant_concentration_pct}%
              </div>
              <div className="text-xs text-slate-500 mt-1">
                Top 1: {patternsData.top_merchant_concentration_pct}%
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
              <h3 className="font-semibold text-slate-900">Top Merchants by Spend</h3>
              {patternsData.by_merchant.slice(0, 8).map((m) => (
                <div key={m.label} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-slate-800">
                      {m.label} ({m.transaction_count})
                    </span>
                    <span className="font-semibold text-slate-900">
                      {formatINR(m.amount)} ({m.share_pct}%)
                    </span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${Math.min(100, Number(m.share_pct))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
              <h3 className="font-semibold text-slate-900">Day of Week Spending Distribution</h3>
              {patternsData.day_of_week_trend.map((d) => {
                const maxAmt = Math.max(
                  1,
                  ...patternsData.day_of_week_trend.map((x) => Number(x.total_expense))
                );
                const pct = (Number(d.total_expense) / maxAmt) * 100;
                return (
                  <div key={d.day_index} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-slate-700">
                        {d.day_name} ({d.transaction_count})
                      </span>
                      <span className="font-semibold text-slate-900">{formatINR(d.total_expense)}</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-violet-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* 6. ANOMALIES TAB */}
      {activeTab === 'anomalies' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {['', 'open', 'acknowledged', 'dismissed'].map((st) => (
                <button
                  key={st || 'all'}
                  type="button"
                  onClick={() => setAnomalyFilter(st)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border ${
                    anomalyFilter === st
                      ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                      : 'bg-white text-slate-600 border-slate-200'
                  }`}
                >
                  {st ? st.toUpperCase() : 'ALL'}
                </button>
              ))}
            </div>
            <span className="text-xs text-slate-500">
              Statistical baseline deviations only — never automated fraud accusations
            </span>
          </div>

          <div className="space-y-3">
            {!anomaliesData || anomaliesData.items.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-sm text-slate-500">
                No statistical spending anomalies detected for this filter.
              </div>
            ) : (
              anomaliesData.items.map((a) => (
                <div key={a.id} className="bg-white rounded-xl border border-slate-200 p-4 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 text-xs font-semibold rounded border uppercase ${
                          SEVERITY_BADGE[a.severity] || SEVERITY_BADGE.medium
                        }`}
                      >
                        {a.severity}
                      </span>
                      <span className="font-semibold text-slate-900">
                        {a.category_name || 'Spending'} {a.merchant_name ? `• ${a.merchant_name}` : ''}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">{a.detection_method}</span>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 capitalize">
                      {a.review_status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700">{a.explanation}</p>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 pt-1">
                    <div>
                      Observed: <strong className="text-slate-900">{formatINR(a.observed_amount)}</strong> •
                      Baseline: {formatINR(a.baseline_amount)} • Deviation:{' '}
                      <strong className="text-rose-700">+{a.deviation_pct}%</strong>
                    </div>
                    <div className="flex items-center gap-2">
                      {a.review_status === 'open' ? (
                        <>
                          <button
                            type="button"
                            onClick={() => handleAnomalyAction(a.id, 'acknowledge')}
                            className="px-2.5 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200"
                          >
                            Acknowledge
                          </button>
                          <button
                            type="button"
                            onClick={() => handleAnomalyAction(a.id, 'dismiss')}
                            className="px-2.5 py-1 rounded bg-slate-100 text-slate-700 border border-slate-200"
                          >
                            Dismiss
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleAnomalyAction(a.id, 'reopen')}
                          className="px-2.5 py-1 rounded bg-white text-slate-700 border border-slate-200"
                        >
                          Reopen
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 7. INSIGHTS TAB */}
      {activeTab === 'insights' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-2">
            {['', 'new', 'read', 'dismissed'].map((st) => (
              <button
                key={st || 'all'}
                type="button"
                onClick={() => setInsightFilter(st)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border ${
                  insightFilter === st
                    ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                    : 'bg-white text-slate-600 border-slate-200'
                }`}
              >
                {st ? st.toUpperCase() : 'ALL'}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {!insightsData || insightsData.items.length === 0 ? (
              <div className="md:col-span-2 bg-white rounded-xl border border-slate-200 p-8 text-center text-sm text-slate-500">
                No financial insights generated for this filter yet.
              </div>
            ) : (
              insightsData.items.map((ins) => (
                <div key={ins.id} className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 text-[11px] font-semibold rounded border uppercase ${
                            SEVERITY_BADGE[ins.severity] || SEVERITY_BADGE.info
                          }`}
                        >
                          {ins.insight_type.replace('_', ' ')}
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono">{ins.provider_name || 'local'}</span>
                      </div>
                      <h4 className="font-semibold text-slate-900">{ins.title}</h4>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 capitalize">
                      {ins.status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-600">{ins.description}</p>
                  {ins.suggested_action && (
                    <div className="p-2.5 rounded-lg bg-indigo-50/70 border border-indigo-100 text-xs text-indigo-800">
                      <strong>Suggested Action:</strong> {ins.suggested_action}
                    </div>
                  )}
                  <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" /> {(Number(ins.confidence) * 100).toFixed(0)}% confidence
                    </span>
                    <div className="flex items-center gap-2">
                      {ins.status === 'new' && (
                        <button
                          type="button"
                          onClick={() => handleInsightAction(ins.id, 'mark_read')}
                          className="px-2.5 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200"
                        >
                          Mark Read
                        </button>
                      )}
                      {ins.status !== 'dismissed' ? (
                        <button
                          type="button"
                          onClick={() => handleInsightAction(ins.id, 'dismiss')}
                          className="px-2.5 py-1 rounded bg-slate-100 text-slate-700 border border-slate-200"
                        >
                          Dismiss
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleInsightAction(ins.id, 'reopen')}
                          className="px-2.5 py-1 rounded bg-white text-slate-700 border border-slate-200"
                        >
                          Reopen
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Override Transaction Modal */}
      {editingTx && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <form
            onSubmit={handleSubmitOverride}
            className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">Override Category & Merchant</h3>
              <button type="button" onClick={() => setEditingTx(null)}>
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg">
              <div>
                <strong>{editingTx.description || editingTx.merchant_payee}</strong>
              </div>
              <div className="mt-0.5">
                {formatINR(editingTx.amount)} • {formatDate(editingTx.transaction_date)}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Category</label>
              <select
                required
                value={overrideCategoryId}
                onChange={(e) => setOverrideCategoryId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              >
                <option value="">Select category...</option>
                {categories
                  .filter((c) => c.category_type === editingTx.transaction_type)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Normalized Merchant Name
              </label>
              <input
                type="text"
                value={overrideMerchantName}
                onChange={(e) => setOverrideMerchantName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={saveMerchantMapping}
                onChange={(e) => setSaveMerchantMapping(e.target.checked)}
              />
              <span>Remember this category for future transactions from this merchant</span>
            </label>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Notes (optional)</label>
              <input
                type="text"
                value={overrideNotes}
                onChange={(e) => setOverrideNotes(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setEditingTx(null)}
                className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-sm rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700"
              >
                Save Feedback
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Edit Merchant Modal */}
      {editingMerchant && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <form
            onSubmit={handleSaveMerchant}
            className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">Edit Normalized Merchant</h3>
              <button type="button" onClick={() => setEditingMerchant(null)}>
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Display Merchant Name
              </label>
              <input
                type="text"
                required
                value={editMerchName}
                onChange={(e) => setEditMerchName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Default Expense Category
              </label>
              <select
                value={editMerchCatId}
                onChange={(e) => setEditMerchCatId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              >
                <option value="">Keep current</option>
                {categories
                  .filter((c) => c.category_type === 'expense')
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setEditingMerchant(null)}
                className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-sm rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700"
              >
                Save Mapping
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
