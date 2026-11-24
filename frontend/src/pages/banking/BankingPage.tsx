import React, { useState, useEffect } from 'react';
import {
  Landmark,
  ShieldCheck,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Download,
  Check,
  X,
  Unplug,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import {
  BankingConnection,
  BankingProviderInfo,
  DiscoveredAccount,
} from '../../types/finance';
import { formatINR, formatDate } from '../../lib/formatters';

interface BankingPageProps {
  onNavigate: (view: string) => void;
}

export const BankingPage: React.FC<BankingPageProps> = ({ onNavigate }) => {
  const [providers, setProviders] = useState<BankingProviderInfo[]>([]);
  const [connections, setConnections] = useState<BankingConnection[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState<string | null>(null);

  // Connect modal
  const [selectedProvider, setSelectedProvider] = useState<BankingProviderInfo | null>(null);
  const [consentChecked, setConsentChecked] = useState<boolean>(false);
  const [isConnecting, setIsConnecting] = useState<boolean>(false);

  // Discover accounts modal
  const [activeConnectionForDiscovery, setActiveConnectionForDiscovery] =
    useState<BankingConnection | null>(null);
  const [discoveredAccounts, setDiscoveredAccounts] = useState<DiscoveredAccount[]>([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false);
  const [isImporting, setIsImporting] = useState<boolean>(false);

  const loadBankingData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [provList, connList] = await Promise.all([
        financeApi.listBankingProviders(),
        financeApi.listBankingConnections(),
      ]);
      setProviders(provList);
      setConnections(connList);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load banking connections.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadBankingData();
  }, []);

  const handleOpenConnect = (prov: BankingProviderInfo) => {
    setSelectedProvider(prov);
    setConsentChecked(false);
  };

  const handleConnectProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProvider || !consentChecked) return;

    setIsConnecting(true);
    try {
      await financeApi.connectDemoProvider(selectedProvider.provider_id, true);
      setSelectedProvider(null);
      await loadBankingData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to establish demo connection.';
      alert(msg);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleOpenDiscover = async (conn: BankingConnection) => {
    setActiveConnectionForDiscovery(conn);
    setIsDiscovering(true);
    setSelectedAccountIds([]);
    try {
      const accounts = await financeApi.discoverBankingAccounts(conn.id);
      setDiscoveredAccounts(accounts);
      // Pre-select accounts that are not yet imported
      const unimported = accounts.filter((a) => !a.already_imported).map((a) => a.external_account_id);
      setSelectedAccountIds(unimported);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to discover accounts.';
      alert(msg);
      setActiveConnectionForDiscovery(null);
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleImportSelected = async () => {
    if (!activeConnectionForDiscovery || selectedAccountIds.length === 0) return;

    setIsImporting(true);
    try {
      await financeApi.importBankingAccounts(
        activeConnectionForDiscovery.id,
        selectedAccountIds
      );
      setActiveConnectionForDiscovery(null);
      await loadBankingData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to import accounts.';
      alert(msg);
    } finally {
      setIsImporting(false);
    }
  };

  const handleSyncConnection = async (connId: string) => {
    setIsSyncing(connId);
    setSyncMessage(null);
    try {
      const res = await financeApi.syncBankingConnection(connId);
      setSyncMessage(res.message);
      await loadBankingData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Sync failed.';
      alert(msg);
    } finally {
      setIsSyncing(null);
    }
  };

  const handleDisconnect = async (connId: string) => {
    if (confirm('Disconnect this simulated banking connection? Existing imported records will be preserved.')) {
      try {
        await financeApi.disconnectBankingConnection(connId);
        await loadBankingData();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to disconnect.';
        alert(msg);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Simulation Banner */}
      <div className="p-4 bg-purple-50 border border-purple-200 rounded-2xl flex items-start space-x-3.5 shadow-sm">
        <ShieldCheck className="w-5 h-5 text-purple-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h2 className="text-sm font-bold text-purple-900">
            Simulated Indian Banking Environment
          </h2>
          <p className="text-xs text-purple-700 mt-0.5 leading-relaxed">
            This module simulates realistic Indian PSU, Private, and Neobank integrations for development and testing.
            <strong> No real banking infrastructure, live networks, or credentials (passwords/PINs/OTPs) are accessed.</strong> All synchronized accounts and transactions are tagged as simulated.
          </p>
        </div>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Simulated Bank Connections</h1>
          <p className="text-sm text-gray-600 mt-1">
            Connect simulated Indian financial institutions, discover accounts, and run idempotent transaction synchronizations.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => onNavigate('accounts')}
            className="px-3 py-2 bg-white text-gray-700 hover:bg-gray-50 border border-gray-200 rounded-lg shadow-sm text-xs font-medium"
          >
            View Accounts &rarr;
          </button>
          <button
            onClick={loadBankingData}
            disabled={isLoading}
            className="p-2 text-gray-500 hover:text-gray-700 bg-white border border-gray-200 rounded-lg shadow-sm hover:bg-gray-50 flex items-center space-x-1.5 text-xs font-medium"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {syncMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{syncMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Active Connections */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-gray-900">Active Connections</h2>

        {connections.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-8 text-center text-gray-500">
            <Landmark className="w-10 h-10 mx-auto text-gray-300 mb-2" />
            <p className="text-sm font-medium text-gray-700">No active bank connections</p>
            <p className="text-xs text-gray-500 mt-1">
              Select one of the simulated demo institutions below to test account discovery and synchronization.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {connections.map((conn) => (
              <div
                key={conn.id}
                className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-4"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center font-bold">
                      <Landmark className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900 text-sm leading-tight">
                        {conn.institution_name}
                      </h3>
                      <div className="text-xs text-gray-500 mt-0.5">
                        Connected: {formatDate(conn.consent_granted_at)}
                      </div>
                    </div>
                  </div>

                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                      conn.status === 'connected'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {conn.status}
                  </span>
                </div>

                <div className="text-xs text-gray-600 bg-gray-50 p-3 rounded-lg flex items-center justify-between">
                  <div>
                    <span className="font-semibold">Imported Accounts:</span>{' '}
                    {conn.connected_accounts_count}
                  </div>
                  <div>
                    <span className="font-semibold">Last Sync:</span>{' '}
                    {conn.last_sync_at ? formatDate(conn.last_sync_at) : 'Never'}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-gray-100 text-xs">
                  {conn.status === 'connected' && (
                    <>
                      <button
                        onClick={() => handleOpenDiscover(conn)}
                        className="px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg font-medium transition-colors flex items-center space-x-1"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Discover Accounts</span>
                      </button>

                      <button
                        onClick={() => handleSyncConnection(conn.id)}
                        disabled={isSyncing === conn.id}
                        className="px-3 py-1.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg font-medium transition-colors flex items-center space-x-1"
                      >
                        <RefreshCw
                          className={`w-3.5 h-3.5 ${isSyncing === conn.id ? 'animate-spin' : ''}`}
                        />
                        <span>Sync Now</span>
                      </button>

                      <button
                        onClick={() => handleDisconnect(conn.id)}
                        className="px-3 py-1.5 text-gray-500 hover:text-red-700 hover:bg-red-50 rounded-lg font-medium transition-colors ml-auto flex items-center space-x-1"
                      >
                        <Unplug className="w-3.5 h-3.5" />
                        <span>Disconnect</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Available Demo Providers */}
      <div className="space-y-4 pt-4">
        <h2 className="text-base font-bold text-gray-900">Available Simulated Providers</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {providers.map((prov) => {
            const isConnected = connections.some(
              (c) => c.provider_id === prov.provider_id && c.status === 'connected'
            );

            return (
              <div
                key={prov.provider_id}
                className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow transition-shadow flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                      <Landmark className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900 text-sm">{prov.name}</h3>
                      <span className="text-[10px] uppercase font-bold text-purple-700 tracking-wider">
                        Simulated Bank
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-gray-600 mt-3 leading-relaxed">
                    {prov.description}
                  </p>

                  <div className="mt-3 flex flex-wrap gap-1">
                    {prov.supported_account_types.map((type) => (
                      <span
                        key={type}
                        className="px-2 py-0.5 bg-gray-100 text-gray-600 text-[10px] font-medium rounded capitalize"
                      >
                        {type.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-gray-100">
                  {isConnected ? (
                    <span className="text-xs font-semibold text-emerald-600 flex items-center space-x-1">
                      <Check className="w-4 h-4" />
                      <span>Connected</span>
                    </span>
                  ) : (
                    <button
                      onClick={() => handleOpenConnect(prov)}
                      className="w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium rounded-lg shadow-sm transition-colors"
                    >
                      Connect Simulation
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Connect Confirmation & Consent Modal */}
      {selectedProvider && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <button
              onClick={() => setSelectedProvider(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center mb-3">
              <Landmark className="w-5 h-5" />
            </div>

            <h3 className="text-base font-bold text-gray-900">
              Connect {selectedProvider.name}
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              Initialize a simulated sandbox connection to discover demo accounts and realistic transactions.
            </p>

            <form onSubmit={handleConnectProvider} className="mt-5 space-y-4">
              <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-700 space-y-2">
                <div className="font-semibold text-gray-900">Simulation Disclaimers:</div>
                <ul className="list-disc pl-4 space-y-1 text-gray-600">
                  <li>No real bank account or credentials will be accessed.</li>
                  <li>All imported records will be labeled as &ldquo;Demo Bank&rdquo;.</li>
                  <li>You can disconnect at any time without losing historical ledger records.</li>
                </ul>
              </div>

              <div className="flex items-start space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="consent"
                  required
                  checked={consentChecked}
                  onChange={(e) => setConsentChecked(e.target.checked)}
                  className="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="consent" className="text-xs text-gray-700 leading-tight">
                  I understand this is a simulation and consent to adding demo accounts and transactions to my workspace.
                </label>
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setSelectedProvider(null)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!consentChecked || isConnecting}
                  className="px-4 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm flex items-center space-x-1"
                >
                  {isConnecting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Authorize & Connect</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Account Discovery & Import Modal */}
      {activeConnectionForDiscovery && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl relative animate-in fade-in zoom-in duration-150">
            <button
              onClick={() => setActiveConnectionForDiscovery(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-bold text-gray-900">
              Discovered Accounts from {activeConnectionForDiscovery.institution_name}
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              Select which demo accounts you want to import into your financial ledger.
            </p>

            <div className="mt-4 max-h-60 overflow-y-auto space-y-2.5">
              {isDiscovering ? (
                <div className="py-8 text-center text-gray-400 text-xs">
                  <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
                  <span>Discovering provider accounts...</span>
                </div>
              ) : discoveredAccounts.length === 0 ? (
                <div className="py-6 text-center text-gray-500 text-xs">
                  No accounts found for this provider.
                </div>
              ) : (
                discoveredAccounts.map((acc) => {
                  const isChecked = selectedAccountIds.includes(acc.external_account_id);
                  return (
                    <div
                      key={acc.external_account_id}
                      className={`p-3 rounded-lg border flex items-center justify-between text-xs transition-colors ${
                        acc.already_imported
                          ? 'bg-gray-50 border-gray-200 opacity-60'
                          : isChecked
                          ? 'bg-blue-50/60 border-blue-300'
                          : 'bg-white border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <input
                          type="checkbox"
                          disabled={acc.already_imported}
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedAccountIds([...selectedAccountIds, acc.external_account_id]);
                            } else {
                              setSelectedAccountIds(
                                selectedAccountIds.filter((id) => id !== acc.external_account_id)
                              );
                            }
                          }}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <div>
                          <div className="font-semibold text-gray-900">{acc.name}</div>
                          <div className="text-gray-500 text-[11px]">
                            {acc.account_type.toUpperCase()} • {acc.masked_account_number}
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="font-bold text-gray-900">{formatINR(acc.balance)}</div>
                        {acc.already_imported && (
                          <span className="text-[10px] text-gray-500 italic">Already Imported</span>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="mt-5 pt-3 border-t border-gray-100 flex items-center justify-between">
              <span className="text-xs text-gray-500">
                {selectedAccountIds.length} account(s) selected
              </span>

              <div className="flex space-x-2">
                <button
                  type="button"
                  onClick={() => setActiveConnectionForDiscovery(null)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={selectedAccountIds.length === 0 || isImporting}
                  onClick={handleImportSelected}
                  className="px-4 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg shadow-sm flex items-center space-x-1"
                >
                  {isImporting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Import Selected</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
