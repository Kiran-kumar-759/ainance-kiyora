import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ExternalLink,
  Globe,
  Info,
  Landmark,
  Mail,
  MessageSquare,
  Plug,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Unplug,
  X,
  XCircle,
} from 'lucide-react';
import { assistantApi } from '../../services/assistantApi';
import { emailIngestionApi } from '../../services/documentsApi';
import { integrationsApi } from '../../services/integrationsApi';
import { WebProviderId } from '../../types/assistant';
import {
  IntegrationCategory,
  IntegrationConnectionSummary,
  IntegrationItem,
  IntegrationsOverview,
  IntegrationStatus,
  IntegrationTestResult,
} from '../../types/integrations';

interface IntegrationsPageProps {
  onNavigate: (view: string) => void;
}

const CATEGORY_TABS: { id: 'all' | IntegrationCategory; label: string }[] = [
  { id: 'all', label: 'All Integrations' },
  { id: 'web_research', label: 'Web Research' },
  { id: 'banking', label: 'Banking' },
  { id: 'email', label: 'Email (Gmail)' },
  { id: 'ai', label: 'AI Provider' },
  { id: 'sms', label: 'SMS' },
  { id: 'notifications', label: 'SMTP Delivery' },
];

const STATUS_BADGE: Record<IntegrationStatus, { label: string; classes: string }> = {
  connected: {
    label: 'Connected',
    classes: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
  available: {
    label: 'Available',
    classes: 'bg-sky-50 text-sky-700 border-sky-200',
  },
  configured_not_connected: {
    label: 'Configured (Not Connected)',
    classes: 'bg-amber-50 text-amber-800 border-amber-200',
  },
  unavailable: {
    label: 'Unavailable',
    classes: 'bg-slate-100 text-slate-600 border-slate-200',
  },
  error: {
    label: 'Needs Attention',
    classes: 'bg-rose-50 text-rose-700 border-rose-200',
  },
  planned: {
    label: 'Planned / Future',
    classes: 'bg-purple-50 text-purple-700 border-purple-200',
  },
};

function categoryIcon(category: IntegrationCategory) {
  switch (category) {
    case 'banking':
      return Landmark;
    case 'email':
      return Mail;
    case 'sms':
      return MessageSquare;
    case 'ai':
      return Bot;
    case 'web_research':
      return Globe;
    case 'notifications':
      return Send;
  }
}

export const IntegrationsPage: React.FC<IntegrationsPageProps> = ({ onNavigate }) => {
  const [overview, setOverview] = useState<IntegrationsOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<'all' | IntegrationCategory>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, IntegrationTestResult>>({});
  const [savingWebPref, setSavingWebPref] = useState(false);
  const [connectingGmail, setConnectingGmail] = useState(false);

  const [selectedDetail, setSelectedDetail] = useState<IntegrationItem | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState<IntegrationConnectionSummary | null>(null);
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadOverview = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await integrationsApi.getOverview();
      setOverview(data);
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : 'Unable to load integrations overview.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const handleTestProvider = async (providerId: string) => {
    setTestingId(providerId);
    setBanner(null);
    try {
      const result = await integrationsApi.testProvider(providerId);
      setTestResults((prev) => ({ ...prev, [providerId]: result }));
      setBanner({
        type: result.success ? 'success' : 'error',
        text: `${result.message}${result.latency_ms !== null ? ` (${result.latency_ms} ms)` : ''}`,
      });
    } catch (err: unknown) {
      setBanner({
        type: 'error',
        text: err instanceof Error ? err.message : 'Provider connectivity check failed.',
      });
    } finally {
      setTestingId(null);
    }
  };

  const handleSelectPreferredWeb = async (providerId: WebProviderId) => {
    setSavingWebPref(true);
    setBanner(null);
    try {
      const updated = await assistantApi.updatePreferences({ default_web_provider: providerId });
      setOverview((prev) =>
        prev
          ? {
              ...prev,
              preferred_web_provider: updated.default_web_provider,
              integrations: prev.integrations.map((item) =>
                item.category === 'web_research'
                  ? { ...item, is_preferred: item.provider_id === updated.default_web_provider }
                  : item
              ),
            }
          : prev
      );
      setBanner({
        type: 'success',
        text: `Preferred AI Assistant web research provider set to ${providerId} (no silent fallback enabled).`,
      });
    } catch (err: unknown) {
      setBanner({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to update preferred web research provider.',
      });
    } finally {
      setSavingWebPref(false);
    }
  };

  const handleToggleWebSearch = async (nextEnabled: boolean) => {
    setSavingWebPref(true);
    setBanner(null);
    try {
      const updated = await assistantApi.updatePreferences({ web_search_enabled: nextEnabled });
      setOverview((prev) =>
        prev ? { ...prev, web_search_enabled: updated.web_search_enabled } : prev
      );
      setBanner({
        type: 'success',
        text: updated.web_search_enabled
          ? 'External web research enabled for AI Assistant queries.'
          : 'External web research disabled; AI Assistant will rely solely on your personal records & documents.',
      });
    } catch (err: unknown) {
      setBanner({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to toggle web research preference.',
      });
    } finally {
      setSavingWebPref(false);
    }
  };

  const handleConnectGmail = async () => {
    setConnectingGmail(true);
    setBanner(null);
    try {
      const res = await emailIngestionApi.getGmailConnectUrl();
      if (typeof window !== 'undefined' && res.authorization_url) {
        window.open(res.authorization_url, '_blank', 'noopener,noreferrer');
      }
      setBanner({
        type: 'success',
        text: 'Gmail read-only OAuth consent opened in a new tab. Complete authorization and click Refresh.',
      });
    } catch (err: unknown) {
      setBanner({
        type: 'error',
        text: err instanceof Error ? err.message : 'Unable to start Gmail OAuth connect flow.',
      });
    } finally {
      setConnectingGmail(false);
    }
  };

  const handleDisconnectConnection = async () => {
    if (!confirmDisconnect) return;
    setDisconnectingId(confirmDisconnect.connection_id);
    setBanner(null);
    try {
      const res = await integrationsApi.disconnectConnection(confirmDisconnect.connection_id);
      setBanner({ type: 'success', text: res.message });
      setConfirmDisconnect(null);
      await loadOverview();
    } catch (err: unknown) {
      setBanner({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to disconnect integration.',
      });
    } finally {
      setDisconnectingId(null);
    }
  };

  const filteredIntegrations = useMemo(() => {
    if (!overview) return [];
    const q = searchQuery.trim().toLowerCase();
    return overview.integrations.filter((item) => {
      if (selectedCategory !== 'all' && item.category !== selectedCategory) return false;
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.provider_id.toLowerCase().includes(q) ||
        item.capabilities.some((c) => c.toLowerCase().includes(q))
      );
    });
  }, [overview, selectedCategory, searchQuery]);

  const webProviders = useMemo(
    () => (overview?.integrations || []).filter((i) => i.category === 'web_research'),
    [overview]
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
            <Plug className="w-5 h-5 text-indigo-600" />
            <span>Integrations Center</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Inspect live configuration readiness, test server-side providers, and manage Banking, Gmail, SMS, Groq AI, Web Research, and SMTP connections.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 self-start">
          <button
            type="button"
            onClick={() => onNavigate('reminders')}
            className="inline-flex items-center space-x-1.5 px-3 py-2 text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Reminders &amp; Delivery &rarr;</span>
          </button>
          <button
            type="button"
            onClick={() => void loadOverview()}
            disabled={isLoading}
            className="inline-flex items-center space-x-1.5 px-3 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition-colors shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-indigo-600' : ''}`} />
            <span>Refresh Status</span>
          </button>
        </div>
      </div>

      {banner && (
        <div
          role="status"
          className={`p-3 rounded-xl border text-xs flex items-center space-x-2 ${
            banner.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-rose-50 text-rose-800 border-rose-200'
          }`}
        >
          {banner.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          )}
          <span>{banner.text}</span>
        </div>
      )}

      {loadError && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center justify-between">
          <span>{loadError}</span>
          <button
            type="button"
            onClick={() => void loadOverview()}
            className="px-3 py-1 bg-white border border-rose-200 rounded-lg font-medium hover:bg-rose-100"
          >
            Retry
          </button>
        </div>
      )}

      {/* Integration Dashboard Summary KPIs */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-xs">
            <div className="text-[11px] font-medium text-slate-500">Available Integrations</div>
            <div className="text-2xl font-bold text-slate-900 mt-1">{overview.total_integrations}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              +{overview.planned_count} planned future
            </div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-xs">
            <div className="text-[11px] font-medium text-slate-500">Configured</div>
            <div className="text-2xl font-bold text-sky-700 mt-1">{overview.configured_count}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">Server keys / setup present</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-xs">
            <div className="text-[11px] font-medium text-slate-500">Connected</div>
            <div className="text-2xl font-bold text-emerald-700 mt-1">{overview.connected_count}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">Active sessions / grants</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-xs">
            <div className="text-[11px] font-medium text-slate-500">Unavailable</div>
            <div className="text-2xl font-bold text-slate-700 mt-1">{overview.unavailable_count}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">Missing keys or disabled</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-xs col-span-2 sm:col-span-1">
            <div className="text-[11px] font-medium text-slate-500">Needs Attention</div>
            <div
              className={`text-2xl font-bold mt-1 ${
                overview.attention_required_count > 0 ? 'text-amber-600' : 'text-slate-700'
              }`}
            >
              {overview.attention_required_count}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">Errors or pending grant</div>
          </div>
        </div>
      )}

      {/* Web Research Provider Selection Panel */}
      {overview && webProviders.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center space-x-2">
                <Globe className="w-4 h-4 text-emerald-600" />
                <span>AI Assistant Web Research Provider Selection</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Choose the default web search provider used by the Phase 10 AI Assistant. Selected providers never fall back silently to another provider if unavailable.
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <label className="inline-flex items-center space-x-2 text-xs font-medium text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={overview.web_search_enabled}
                  disabled={savingWebPref}
                  onChange={(e) => void handleToggleWebSearch(e.target.checked)}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span>Web Research Enabled</span>
              </label>
              <button
                type="button"
                onClick={() => onNavigate('assistant')}
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Open AI Assistant</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {webProviders.map((wp) => {
              const selected = overview.preferred_web_provider === wp.provider_id;
              const badge = STATUS_BADGE[wp.status];
              return (
                <div
                  key={wp.provider_id}
                  className={`rounded-xl border p-3.5 transition-all ${
                    selected
                      ? 'border-emerald-500 bg-emerald-50/40 ring-1 ring-emerald-500/20'
                      : 'border-slate-200 bg-slate-50/40'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-xs font-semibold text-slate-900 flex items-center space-x-1.5">
                        <span>{wp.name}</span>
                        {selected && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-600 text-white font-semibold">
                            Preferred
                          </span>
                        )}
                      </div>
                      <span
                        className={`inline-block mt-1 text-[10px] font-medium px-2 py-0.5 rounded-full border ${badge.classes}`}
                      >
                        {badge.label}
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-600 mt-2 line-clamp-2">{wp.description}</p>
                  {!wp.available && wp.required_env_vars.length > 0 && (
                    <p className="text-[10px] text-amber-700 mt-1.5 font-mono">
                      Requires server env: {wp.required_env_vars.join(', ')}
                    </p>
                  )}
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      disabled={selected || savingWebPref}
                      onClick={() => void handleSelectPreferredWeb(wp.provider_id as WebProviderId)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-colors ${
                        selected
                          ? 'bg-emerald-600 text-white cursor-default'
                          : 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {selected ? 'Active Default' : 'Select Provider'}
                    </button>
                    <button
                      type="button"
                      disabled={testingId === wp.provider_id}
                      onClick={() => void handleTestProvider(wp.provider_id)}
                      className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {testingId === wp.provider_id ? 'Testing...' : 'Test Connection'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Search & Category Filter Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Integration categories">
          {CATEGORY_TABS.map((tab) => {
            const active = selectedCategory === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setSelectedCategory(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  active
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="relative w-full md:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search integrations..."
            aria-label="Search integrations"
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
          />
        </div>
      </div>

      {/* Integration Cards Grid */}
      {isLoading && !overview ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-xs text-slate-500">
          <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin mx-auto mb-2" />
          Loading backend integration statuses...
        </div>
      ) : filteredIntegrations.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-xs text-slate-500">
          No integrations match the selected filter criteria.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredIntegrations.map((item) => {
            const Icon = categoryIcon(item.category);
            const badge = STATUS_BADGE[item.status];
            const lastTest = testResults[item.provider_id];
            return (
              <div
                key={item.provider_id}
                className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-5 flex flex-col justify-between space-y-4"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start space-x-3">
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-700">
                        <Icon className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center flex-wrap gap-1.5">
                          <h3 className="text-sm font-semibold text-slate-900">{item.name}</h3>
                          {item.is_preferred && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white font-medium">
                              Active Default
                            </span>
                          )}
                        </div>
                        <span
                          className={`inline-block mt-1 text-[10px] font-medium px-2 py-0.5 rounded-full border ${badge.classes}`}
                        >
                          {badge.label}
                        </span>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => setSelectedDetail(item)}
                      className="text-[11px] font-medium text-slate-600 hover:text-slate-900 inline-flex items-center space-x-1 px-2 py-1 rounded-lg hover:bg-slate-100"
                    >
                      <Info className="w-3.5 h-3.5" />
                      <span>Details</span>
                    </button>
                  </div>

                  <p className="text-xs text-slate-600 leading-relaxed">{item.description}</p>

                  {/* Safe Metadata Preview */}
                  <div className="flex flex-wrap gap-1.5">
                    {item.capabilities.map((cap) => (
                      <span
                        key={cap}
                        className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/70"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>

                  {item.last_error && (
                    <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-800">
                      {item.last_error}
                    </div>
                  )}

                  {!item.available && item.required_env_vars.length > 0 && (
                    <div className="text-[11px] text-slate-500 bg-slate-50 border border-slate-200/80 rounded-lg px-2.5 py-1.5 font-mono">
                      Required env: {item.required_env_vars.join(', ')}
                    </div>
                  )}

                  {lastTest && (
                    <div
                      className={`p-2 rounded-lg border text-[11px] flex items-center space-x-1.5 ${
                        lastTest.success
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                          : 'bg-rose-50 border-rose-200 text-rose-800'
                      }`}
                    >
                      {lastTest.success ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-600 flex-shrink-0" />
                      )}
                      <span>{lastTest.message}</span>
                    </div>
                  )}
                </div>

                {/* Action Footer */}
                <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[11px] text-slate-400">
                    {item.last_sync_or_test_at
                      ? `Last activity: ${new Date(item.last_sync_or_test_at).toLocaleString('en-IN')}`
                      : item.is_planned
                      ? 'Future roadmap integration'
                      : 'Server-side credentials never exposed'}
                  </span>

                  <div className="flex items-center space-x-2">
                    {item.provider_id === 'demo_banking' && (
                      <button
                        type="button"
                        onClick={() => onNavigate('banking')}
                        className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>Manage Bank Feeds</span>
                      </button>
                    )}
                    {item.provider_id === 'gmail' && item.can_connect && (
                      <button
                        type="button"
                        disabled={connectingGmail}
                        onClick={() => void handleConnectGmail()}
                        className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg disabled:opacity-50"
                      >
                        <Mail className="w-3 h-3" />
                        <span>{connectingGmail ? 'Opening...' : 'Connect Gmail'}</span>
                      </button>
                    )}
                    {item.provider_id === 'gmail' && item.connected && (
                      <button
                        type="button"
                        onClick={() => onNavigate('documents')}
                        className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>Open Email Sync</span>
                      </button>
                    )}
                    {item.can_test && (
                      <button
                        type="button"
                        disabled={testingId === item.provider_id}
                        onClick={() => void handleTestProvider(item.provider_id)}
                        className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50"
                      >
                        {testingId === item.provider_id ? 'Testing...' : 'Test Connection'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Active User Connections Section */}
      {overview && (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Your Account Connections</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Tenant-owned OAuth grants and simulated banking links. Disconnecting revokes tokens without deleting verified financial records.
              </p>
            </div>
          </div>

          {overview.connections.length === 0 ? (
            <p className="text-xs text-slate-500 py-4 text-center">
              No banking or Gmail OAuth connections established yet.
            </p>
          ) : (
            <div className="divide-y divide-slate-100">
              {overview.connections.map((conn) => (
                <div
                  key={conn.connection_id}
                  className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-semibold text-slate-900">
                        {conn.display_name}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${
                          conn.status === 'connected'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-slate-100 text-slate-600 border-slate-200'
                        }`}
                      >
                        {conn.status}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1 space-x-3">
                      {conn.account_or_email && <span>Account: {conn.account_or_email}</span>}
                      {conn.linked_accounts_count > 0 && (
                        <span>Linked accounts: {conn.linked_accounts_count}</span>
                      )}
                      {conn.last_sync_at && (
                        <span>Last sync: {new Date(conn.last_sync_at).toLocaleString('en-IN')}</span>
                      )}
                    </div>
                    {conn.scopes.length > 0 && (
                      <div className="text-[10px] text-slate-400 mt-0.5 font-mono">
                        Scopes: {conn.scopes.join(', ')}
                      </div>
                    )}
                  </div>

                  {conn.can_disconnect && (
                    <button
                      type="button"
                      onClick={() => setConfirmDisconnect(conn)}
                      className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-lg hover:bg-rose-100 self-start sm:self-center"
                    >
                      <Unplug className="w-3.5 h-3.5" />
                      <span>Disconnect</span>
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Detail & Setup Modal */}
      {selectedDetail && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="integration-detail-title"
        >
          <div className="bg-white rounded-2xl border border-slate-200 max-w-lg w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <h3 id="integration-detail-title" className="text-base font-bold text-slate-900">
                  {selectedDetail.name}
                </h3>
                <p className="text-xs text-slate-500">{selectedDetail.provider_id}</p>
              </div>
              <button
                type="button"
                aria-label="Close detail dialog"
                onClick={() => setSelectedDetail(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-700 leading-relaxed">{selectedDetail.description}</p>

            <div className="bg-slate-50 rounded-xl border border-slate-200 p-3 space-y-1.5">
              <div className="text-[11px] font-semibold text-slate-700">
                Runtime Configuration & Safe Telemetry
              </div>
              {Object.entries(selectedDetail.safe_metadata).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2 text-[11px]">
                  <span className="text-slate-500 font-mono">{k}</span>
                  <span className="text-slate-800 font-mono text-right break-all">
                    {Array.isArray(v) ? v.join(', ') : String(v ?? '—')}
                  </span>
                </div>
              ))}
            </div>

            {selectedDetail.required_env_vars.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-900">
                <div className="font-semibold mb-1">Server Environment Variables Required</div>
                <p className="font-mono text-[11px]">{selectedDetail.required_env_vars.join(', ')}</p>
                <p className="text-[11px] mt-1 text-amber-800">
                  Configure these server-side only (in runtime environment or <code>backend/.env</code>). Secrets are never returned to the browser.
                </p>
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setSelectedDetail(null)}
                className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
              >
                Close
              </button>
              {selectedDetail.can_test && (
                <button
                  type="button"
                  disabled={testingId === selectedDetail.provider_id}
                  onClick={() => void handleTestProvider(selectedDetail.provider_id)}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                >
                  {testingId === selectedDetail.provider_id ? 'Testing...' : 'Run Connection Test'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Disconnect Confirmation Modal */}
      {confirmDisconnect && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="disconnect-title"
        >
          <div className="bg-white rounded-2xl border border-slate-200 max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 id="disconnect-title" className="text-base font-bold text-slate-900">
              Disconnect {confirmDisconnect.display_name}?
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              This will revoke the active connection and clear server-side OAuth tokens. Your previously imported accounts, transactions, bills, and uploaded documents remain safely preserved.
            </p>
            <div className="flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setConfirmDisconnect(null)}
                className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={disconnectingId === confirmDisconnect.connection_id}
                onClick={() => void handleDisconnectConnection()}
                className="px-3 py-1.5 text-xs font-medium text-white bg-rose-600 rounded-lg hover:bg-rose-700 disabled:opacity-50"
              >
                {disconnectingId === confirmDisconnect.connection_id
                  ? 'Disconnecting...'
                  : 'Confirm Disconnect'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
