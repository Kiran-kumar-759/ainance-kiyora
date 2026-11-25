import React, { useState } from 'react';
import { formatINR } from '../../lib/formatters';
import {
  AccountAnalyticsItem,
  CategoryBreakdownItem,
  ComparisonMetric,
  TimeSeriesPoint,
} from '../../types/analytics';

function toNum(v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0;
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return Number.isFinite(n) ? n : 0;
}

const CHART_COLORS = [
  '#2563eb',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#06b6d4',
  '#ec4899',
  '#64748b',
];

export const EmptyChartState: React.FC<{ message: string }> = ({ message }) => (
  <div className="h-52 flex flex-col items-center justify-center text-center border border-dashed border-gray-200 rounded-xl bg-gray-50/50 px-4">
    <p className="text-xs font-medium text-gray-500">{message}</p>
  </div>
);

interface BarChartProps {
  series: TimeSeriesPoint[];
  periodLabel?: string;
}

export const IncomeVsExpenseBarChart: React.FC<BarChartProps> = ({ series, periodLabel }) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (!series || series.length === 0) {
    return <EmptyChartState message="No income or expense activity recorded for this period." />;
  }

  const maxVal = Math.max(
    1,
    ...series.flatMap((p) => [toNum(p.income), toNum(p.expenses)])
  );

  // Sample labels if many points so axis stays legible on mobile/desktop
  const labelStep = Math.max(1, Math.ceil(series.length / 8));
  const width = 620;
  const height = 220;
  const padL = 12;
  const padR = 12;
  const padT = 18;
  const padB = 34;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const slotW = plotW / series.length;
  const barW = Math.max(4, Math.min(22, slotW * 0.34));

  const hovered = hoveredIdx !== null ? series[hoveredIdx] : null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center space-x-4">
          <span className="inline-flex items-center space-x-1.5 text-gray-600">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" />
            <span>Income</span>
          </span>
          <span className="inline-flex items-center space-x-1.5 text-gray-600">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-500 inline-block" />
            <span>Expenses</span>
          </span>
          {periodLabel && <span className="text-gray-400">• {periodLabel}</span>}
        </div>
        {hovered && (
          <div className="text-[11px] bg-slate-900 text-white px-2.5 py-1 rounded-md shadow-sm">
            <span className="font-semibold mr-2">{hovered.label}:</span>
            <span className="text-emerald-300 mr-2">+{formatINR(hovered.income)}</span>
            <span className="text-rose-300">-{formatINR(hovered.expenses)}</span>
          </div>
        )}
      </div>

      <div className="w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-52 select-none"
          role="img"
          aria-label="Income versus expenses bar chart"
        >
          {[0.25, 0.5, 0.75, 1].map((ratio) => {
            const y = padT + plotH * (1 - ratio);
            return (
              <line
                key={ratio}
                x1={padL}
                x2={width - padR}
                y1={y}
                y2={y}
                stroke="#e2e8f0"
                strokeDasharray="3 3"
              />
            );
          })}
          <line
            x1={padL}
            x2={width - padR}
            y1={padT + plotH}
            y2={padT + plotH}
            stroke="#cbd5e1"
          />

          {series.map((pt, idx) => {
            const inc = toNum(pt.income);
            const exp = toNum(pt.expenses);
            const incH = (inc / maxVal) * plotH;
            const expH = (exp / maxVal) * plotH;
            const centerX = padL + slotW * idx + slotW / 2;

            return (
              <g
                key={pt.bucket_key}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                className="cursor-pointer"
              >
                <rect
                  x={centerX - barW - 1}
                  y={padT + plotH - incH}
                  width={barW}
                  height={Math.max(inc > 0 ? 2 : 0, incH)}
                  rx={3}
                  fill={hoveredIdx === idx ? '#059669' : '#10b981'}
                >
                  <title>{`${pt.label} Income: ${formatINR(pt.income)}`}</title>
                </rect>
                <rect
                  x={centerX + 1}
                  y={padT + plotH - expH}
                  width={barW}
                  height={Math.max(exp > 0 ? 2 : 0, expH)}
                  rx={3}
                  fill={hoveredIdx === idx ? '#dc2626' : '#f43f5e'}
                >
                  <title>{`${pt.label} Expenses: ${formatINR(pt.expenses)}`}</title>
                </rect>
                {idx % labelStep === 0 && (
                  <text
                    x={centerX}
                    y={height - 10}
                    textAnchor="middle"
                    className="fill-gray-500 text-[10px]"
                  >
                    {pt.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};

interface TrendLineChartProps {
  series: TimeSeriesPoint[];
  metric?: 'expenses' | 'income' | 'net_savings';
  color?: string;
  label?: string;
}

export const TrendLineChart: React.FC<TrendLineChartProps> = ({
  series,
  metric = 'expenses',
  color = '#2563eb',
  label = 'Trend',
}) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (!series || series.length === 0) {
    return <EmptyChartState message={`No data available for ${label.toLowerCase()}.`} />;
  }

  const values = series.map((p) => toNum(p[metric]));
  const minVal = Math.min(0, ...values);
  const maxVal = Math.max(1, ...values);
  const span = Math.max(1, maxVal - minVal);

  const width = 600;
  const height = 210;
  const padL = 16;
  const padR = 16;
  const padT = 18;
  const padB = 34;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const labelStep = Math.max(1, Math.ceil(series.length / 7));

  const coords = series.map((pt, i) => {
    const x =
      series.length === 1 ? padL + plotW / 2 : padL + (i / (series.length - 1)) * plotW;
    const val = toNum(pt[metric]);
    const y = padT + plotH - ((val - minVal) / span) * plotH;
    return { x, y, pt, val };
  });

  const polyline = coords.map((c) => `${c.x},${c.y}`).join(' ');
  const hovered = hoveredIdx !== null ? coords[hoveredIdx] : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs min-h-[24px]">
        <span className="font-medium text-gray-600">{label}</span>
        {hovered && (
          <span className="px-2.5 py-0.5 bg-slate-900 text-white rounded text-[11px] font-medium">
            {hovered.pt.label}: {formatINR(hovered.val)}
          </span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-48 select-none"
        role="img"
        aria-label={label}
      >
        <line
          x1={padL}
          x2={width - padR}
          y1={padT + plotH - ((0 - minVal) / span) * plotH}
          y2={padT + plotH - ((0 - minVal) / span) * plotH}
          stroke="#cbd5e1"
          strokeDasharray="4 4"
        />
        {coords.length > 1 && (
          <polyline fill="none" stroke={color} strokeWidth={2.5} points={polyline} />
        )}
        {coords.map((c, idx) => (
          <g
            key={c.pt.bucket_key}
            onMouseEnter={() => setHoveredIdx(idx)}
            onMouseLeave={() => setHoveredIdx(null)}
            className="cursor-pointer"
          >
            <circle
              cx={c.x}
              cy={c.y}
              r={hoveredIdx === idx ? 5.5 : 3.5}
              fill="#ffffff"
              stroke={color}
              strokeWidth={2.5}
            >
              <title>{`${c.pt.label}: ${formatINR(c.val)}`}</title>
            </circle>
            {idx % labelStep === 0 && (
              <text
                x={c.x}
                y={height - 10}
                textAnchor="middle"
                className="fill-gray-500 text-[10px]"
              >
                {c.pt.label}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
};

interface CategoryDonutProps {
  items: CategoryBreakdownItem[];
  totalAmount: string | number;
  onSelectCategory?: (categoryId: string | null, categoryName: string) => void;
}

export const CategoryDonutChart: React.FC<CategoryDonutProps> = ({
  items,
  totalAmount,
  onSelectCategory,
}) => {
  if (!items || items.length === 0 || toNum(totalAmount) <= 0) {
    return <EmptyChartState message="No categorized transactions for this period." />;
  }

  const topItems = items.slice(0, 7);
  const total = toNum(totalAmount);
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  let accumulatedPct = 0;

  return (
    <div className="flex flex-col sm:flex-row items-center gap-6">
      <div className="relative w-40 h-40 flex-shrink-0">
        <svg viewBox="0 0 160 160" className="w-full h-full -rotate-90" role="img" aria-label="Category spending donut chart">
          <circle cx="80" cy="80" r={radius} fill="none" stroke="#f1f5f9" strokeWidth="22" />
          {topItems.map((cat, idx) => {
            const pct = Math.max(0, toNum(cat.total_amount) / total);
            const dash = pct * circumference;
            const offset = -accumulatedPct * circumference;
            accumulatedPct += pct;
            const strokeColor = cat.category_color || CHART_COLORS[idx % CHART_COLORS.length];
            return (
              <circle
                key={`${cat.category_id || 'uncat'}-${idx}`}
                cx="80"
                cy="80"
                r={radius}
                fill="none"
                stroke={strokeColor}
                strokeWidth="22"
                strokeDasharray={`${dash} ${circumference}`}
                strokeDashoffset={offset}
                className={onSelectCategory ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}
                onClick={() => onSelectCategory?.(cat.category_id || null, cat.category_name)}
              >
                <title>{`${cat.category_name}: ${formatINR(cat.total_amount)} (${cat.percentage}%)`}</title>
              </circle>
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none px-2">
          <span className="text-[10px] font-semibold uppercase text-gray-400">Total</span>
          <span className="text-xs font-bold text-gray-900">{formatINR(totalAmount)}</span>
        </div>
      </div>

      <div className="flex-1 w-full space-y-2">
        {topItems.map((cat, idx) => {
          const dotColor = cat.category_color || CHART_COLORS[idx % CHART_COLORS.length];
          return (
            <button
              key={`${cat.category_id || 'uncat'}-legend-${idx}`}
              type="button"
              onClick={() => onSelectCategory?.(cat.category_id || null, cat.category_name)}
              className="w-full flex items-center justify-between text-xs p-1.5 rounded-lg hover:bg-gray-50 transition-colors text-left"
            >
              <span className="flex items-center space-x-2 min-w-0">
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: dotColor }}
                />
                <span className="font-medium text-gray-800 truncate">{cat.category_name}</span>
                <span className="text-[10px] text-gray-400">({cat.transaction_count})</span>
              </span>
              <span className="font-semibold text-gray-900 whitespace-nowrap ml-2">
                {formatINR(cat.total_amount)}{' '}
                <span className="text-gray-400 font-normal">({cat.percentage}%)</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export const HorizontalCategoryBarChart: React.FC<{
  items: CategoryBreakdownItem[];
  onSelectCategory?: (categoryId: string | null, categoryName: string) => void;
}> = ({ items, onSelectCategory }) => {
  if (!items || items.length === 0) {
    return <EmptyChartState message="No category activity to compare." />;
  }

  const maxAmt = Math.max(1, ...items.map((i) => toNum(i.total_amount)));

  return (
    <div className="space-y-3">
      {items.map((cat, idx) => {
        const val = toNum(cat.total_amount);
        const pctWidth = Math.max(2, (val / maxAmt) * 100);
        const color = cat.category_color || CHART_COLORS[idx % CHART_COLORS.length];
        return (
          <div key={`${cat.category_id || 'uncat'}-bar-${idx}`} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <button
                type="button"
                onClick={() => onSelectCategory?.(cat.category_id || null, cat.category_name)}
                className="font-semibold text-gray-800 hover:text-blue-600 text-left inline-flex items-center space-x-1.5"
              >
                <span>{cat.category_name}</span>
                <span className="text-[10px] font-normal text-gray-400">
                  ({cat.transaction_count} txns)
                </span>
              </button>
              <span className="font-bold text-gray-900">
                {formatINR(cat.total_amount)}{' '}
                <span className="text-xs font-normal text-gray-500">({cat.percentage}%)</span>
              </span>
            </div>
            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ width: `${pctWidth}%`, backgroundColor: color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

export const AccountBalanceDistributionChart: React.FC<{
  accounts: AccountAnalyticsItem[];
}> = ({ accounts }) => {
  if (!accounts || accounts.length === 0) {
    return <EmptyChartState message="Create an account to view balance distribution." />;
  }

  const assets = accounts.filter((a) => !a.is_liability);
  const liabilities = accounts.filter((a) => a.is_liability);
  const maxBal = Math.max(1, ...accounts.map((a) => Math.abs(toNum(a.current_balance))));

  return (
    <div className="space-y-4">
      {assets.length > 0 && (
        <div className="space-y-2">
          <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">
            Assets (Available Balances)
          </div>
          {assets.map((a) => {
            const bal = Math.max(0, toNum(a.current_balance));
            const pct = Math.max(2, (bal / maxBal) * 100);
            return (
              <div key={a.account_id} className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="font-medium text-gray-800">{a.name}</span>
                  <span className="font-bold text-emerald-700">{formatINR(a.current_balance)}</span>
                </div>
                <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {liabilities.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-gray-100">
          <div className="text-[11px] font-bold uppercase tracking-wider text-rose-700">
            Liabilities (Credit Card Debt — Not Available Cash)
          </div>
          {liabilities.map((a) => {
            const bal = Math.max(0, toNum(a.current_balance));
            const pct = Math.max(2, (bal / maxBal) * 100);
            return (
              <div key={a.account_id} className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="font-medium text-gray-800">{a.name}</span>
                  <span className="font-bold text-rose-700">-{formatINR(a.current_balance)}</span>
                </div>
                <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-rose-500 rounded-full" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export const PeriodComparisonBarChart: React.FC<{
  currentLabel: string;
  previousLabel: string;
  income: ComparisonMetric;
  expenses: ComparisonMetric;
  netSavings: ComparisonMetric;
}> = ({ currentLabel, previousLabel, income, expenses, netSavings }) => {
  const rows = [
    { label: 'Income', metric: income, color: '#10b981' },
    { label: 'Expenses', metric: expenses, color: '#f43f5e' },
    { label: 'Net Savings', metric: netSavings, color: '#2563eb' },
  ];

  const maxVal = Math.max(
    1,
    ...rows.flatMap((r) => [
      Math.abs(toNum(r.metric.current_value)),
      Math.abs(toNum(r.metric.previous_value)),
    ])
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-4 text-xs">
        <span className="inline-flex items-center space-x-1.5 text-gray-700 font-medium">
          <span className="w-3 h-3 rounded bg-slate-800 inline-block" />
          <span>{currentLabel}</span>
        </span>
        <span className="inline-flex items-center space-x-1.5 text-gray-500">
          <span className="w-3 h-3 rounded bg-slate-300 inline-block" />
          <span>{previousLabel}</span>
        </span>
      </div>

      {rows.map((r) => {
        const cur = Math.max(0, toNum(r.metric.current_value));
        const prev = Math.max(0, toNum(r.metric.previous_value));
        return (
          <div key={r.label} className="space-y-1.5 text-xs">
            <div className="flex justify-between font-medium">
              <span className="text-gray-800">{r.label}</span>
              <span className="text-gray-600">
                {formatINR(r.metric.current_value)} vs {formatINR(r.metric.previous_value)}
              </span>
            </div>
            <div className="space-y-1">
              <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${(cur / maxVal) * 100}%`, backgroundColor: r.color }}
                />
              </div>
              <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-slate-400 rounded-full"
                  style={{ width: `${(prev / maxVal) * 100}%` }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
