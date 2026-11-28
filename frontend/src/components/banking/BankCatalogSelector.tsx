import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  ChevronDown,
  FileSpreadsheet,
  Landmark,
  Plus,
  Search,
  ShieldCheck,
  Smartphone,
} from 'lucide-react';
import { financeApi } from '../../services/financeApi';
import { BankInstitution } from '../../types/finance';

interface BankCatalogSelectorProps {
  selectedBankId?: string;
  onSelectInstitution: (inst: BankInstitution) => void;
  onChooseManualAccount?: (institutionName: string) => void;
  onChooseStatementImport?: (institutionName: string) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  public_sector: 'Public Sector Bank',
  private_sector: 'Private Sector Bank',
  neobank: 'Neobank',
  demo: 'Simulated Demo Bank',
};

function renderBankBadge(inst: BankInstitution) {
  if (inst.is_demo) {
    return (
      <div className="w-9 h-9 rounded-lg bg-purple-100 text-purple-700 border border-purple-200 flex items-center justify-center shrink-0">
        {inst.logo_key === 'smartphone' ? (
          <Smartphone className="w-4 h-4" />
        ) : inst.logo_key === 'building-2' ? (
          <Building2 className="w-4 h-4" />
        ) : (
          <Landmark className="w-4 h-4" />
        )}
      </div>
    );
  }
  const initials = inst.bank_code.slice(0, 4);
  return (
    <div
      className="w-9 h-9 rounded-lg bg-slate-900 text-emerald-300 border border-slate-700 flex items-center justify-center text-[10px] font-bold tracking-tight shrink-0"
      aria-hidden="true"
    >
      {initials}
    </div>
  );
}

export const BankCatalogSelector: React.FC<BankCatalogSelectorProps> = ({
  selectedBankId,
  onSelectInstitution,
  onChooseManualAccount,
  onChooseStatementImport,
}) => {
  const [institutions, setInstitutions] = useState<BankInstitution[]>([]);
  const [search, setSearch] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const loadCatalog = async () => {
      setLoading(true);
      setError(null);
      try {
        if (typeof financeApi.listBankInstitutions !== 'function') {
          if (mounted) setInstitutions([]);
          return;
        }
        const res = await financeApi.listBankInstitutions();
        if (mounted) setInstitutions(res?.institutions || []);
      } catch (err: unknown) {
        if (mounted) {
          setError(
            err instanceof Error ? err.message : 'Unable to load Indian bank catalog.'
          );
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void loadCatalog();
    return () => {
      mounted = false;
    };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return institutions;
    return institutions.filter(
      (i) =>
        i.bank_name.toLowerCase().includes(q) ||
        i.short_name.toLowerCase().includes(q) ||
        i.bank_code.toLowerCase().includes(q) ||
        i.bank_id.toLowerCase().includes(q)
    );
  }, [institutions, search]);

  const selected = useMemo(
    () => institutions.find((i) => i.bank_id === selectedBankId) || null,
    [institutions, selectedBankId]
  );

  return (
    <div className="space-y-3">
      <div>
        <label
          htmlFor="bank-catalog-search"
          className="block text-xs font-semibold text-slate-700 mb-1"
        >
          Search &amp; Select Bank Institution (India)
        </label>
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            id="bank-catalog-search"
            type="text"
            value={search}
            onFocus={() => setDropdownOpen(true)}
            onChange={(e) => {
              setSearch(e.target.value);
              setDropdownOpen(true);
            }}
            placeholder="Search SBI, HDFC, ICICI, Axis, Kotak, or Demo Bank..."
            className="w-full pl-9 pr-9 py-2 text-xs border border-slate-300 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
          <button
            type="button"
            onClick={() => setDropdownOpen((o) => !o)}
            aria-label="Toggle bank list"
            className="absolute right-2.5 top-2 p-0.5 text-slate-400 hover:text-slate-600"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {dropdownOpen && (
        <div className="max-h-56 overflow-y-auto rounded-xl border border-slate-200 bg-white divide-y divide-slate-100 shadow-xs">
          {loading ? (
            <div className="p-4 text-center text-xs text-slate-500">
              Loading bank institutions...
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-500">
              No bank institutions match &ldquo;{search}&rdquo;.
            </div>
          ) : (
            filtered.map((inst) => {
              const isSelected = inst.bank_id === selectedBankId;
              return (
                <button
                  key={inst.bank_id}
                  type="button"
                  onClick={() => {
                    onSelectInstitution(inst);
                    setDropdownOpen(false);
                  }}
                  className={`w-full px-3 py-2.5 flex items-center justify-between gap-3 text-left transition-colors ${
                    isSelected ? 'bg-indigo-50/70' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {renderBankBadge(inst)}
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-slate-900 truncate">
                        {inst.bank_name}
                      </div>
                      <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
                        <span>{CATEGORY_LABELS[inst.category] || inst.category}</span>
                        <span>&bull;</span>
                        <span className="font-mono">{inst.bank_code}</span>
                      </div>
                    </div>
                  </div>
                  <div className="shrink-0">
                    {inst.is_demo ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-50 text-purple-700 border border-purple-200">
                        Demo Ready
                      </span>
                    ) : inst.live_supported ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Live AA Ready
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                        Statement / Manual
                      </span>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>
      )}

      {selected && !selected.is_demo && !selected.live_supported && (
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 space-y-2 text-xs">
          <div className="flex items-start gap-2 text-amber-900">
            <ShieldCheck className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">
                {selected.bank_name}: Direct Live Account Aggregator Feed Not Configured
              </p>
              <p className="text-[11px] text-amber-800 mt-0.5 leading-relaxed">
                {selected.unavailable_reason}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {onChooseManualAccount && (
              <button
                type="button"
                onClick={() => onChooseManualAccount(selected.bank_name)}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-white border border-amber-300 text-amber-900 font-semibold hover:bg-amber-100"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add {selected.short_name} Manually</span>
              </button>
            )}
            {onChooseStatementImport && (
              <button
                type="button"
                onClick={() => onChooseStatementImport(selected.bank_name)}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-white border border-amber-300 text-amber-900 font-semibold hover:bg-amber-100"
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                <span>Import {selected.short_name} Statement</span>
              </button>
            )}
          </div>
        </div>
      )}

      {selected && selected.is_demo && (
        <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200 flex items-center gap-2 text-xs text-emerald-900">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>
            Selected <strong>{selected.bank_name}</strong> (Explicit Simulated Demo Mode — safe sandbox data).
          </span>
        </div>
      )}
    </div>
  );
};
