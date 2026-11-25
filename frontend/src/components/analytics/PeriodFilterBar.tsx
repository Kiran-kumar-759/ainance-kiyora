import React from 'react';
import { ArrowDownRight, ArrowUpRight, Minus, Calendar } from 'lucide-react';
import { ComparisonMetric } from '../../types/analytics';
import { formatINR } from '../../lib/formatters';

export const DASHBOARD_PERIOD_OPTIONS = [
  { id: 'this_week', label: 'This Week' },
  { id: 'this_month', label: 'This Month' },
  { id: 'last_month', label: 'Last Month' },
  { id: 'last_3_months', label: 'Last 3 Months' },
  { id: 'last_6_months', label: 'Last 6 Months' },
  { id: 'this_quarter', label: 'This Quarter' },
  { id: 'last_quarter', label: 'Last Quarter' },
  { id: 'this_year', label: 'This Year' },
  { id: 'last_year', label: 'Last Year' },
  { id: 'all_time', label: 'All Time' },
  { id: 'custom', label: 'Custom Date Range' },
];

interface PeriodFilterBarProps {
  period: string;
  startDate: string;
  endDate: string;
  onPeriodChange: (period: string) => void;
  onStartDateChange: (val: string) => void;
  onEndDateChange: (val: string) => void;
  onApplyCustom?: () => void;
  dateError?: string | null;
}

export const PeriodFilterBar: React.FC<PeriodFilterBarProps> = ({
  period,
  startDate,
  endDate,
  onPeriodChange,
  onStartDateChange,
  onEndDateChange,
  onApplyCustom,
  dateError,
}) => {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2">
      <div className="inline-flex items-center space-x-2 bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 shadow-sm">
        <Calendar className="w-4 h-4 text-gray-500 flex-shrink-0" />
        <select
          aria-label="Select Financial Period"
          value={period}
          onChange={(e) => onPeriodChange(e.target.value)}
          className="text-xs font-medium text-gray-800 bg-transparent focus:outline-none pr-1"
        >
          {DASHBOARD_PERIOD_OPTIONS.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {period === 'custom' && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="date"
            aria-label="Custom Start Date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
          />
          <span className="text-xs text-gray-400">to</span>
          <input
            type="date"
            aria-label="Custom End Date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg bg-white"
          />
          {onApplyCustom && (
            <button
              type="button"
              onClick={onApplyCustom}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg"
            >
              Apply
            </button>
          )}
          {dateError && <span className="text-xs text-rose-600 font-medium">{dateError}</span>}
        </div>
      )}
    </div>
  );
};

export const ComparisonBadge: React.FC<{
  comparison?: ComparisonMetric | null;
  invertGood?: boolean;
}> = ({ comparison, invertGood = false }) => {
  if (!comparison) return null;

  const isUp = comparison.trend_direction === 'up';
  const isDown = comparison.trend_direction === 'down';
  const isGood = invertGood ? isDown : isUp;
  const isBad = invertGood ? isUp : isDown;

  const toneCls = isGood
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : isBad
      ? 'bg-rose-50 text-rose-700 border-rose-200'
      : 'bg-gray-100 text-gray-600 border-gray-200';

  const Icon = isUp ? ArrowUpRight : isDown ? ArrowDownRight : Minus;

  return (
    <span
      className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${toneCls}`}
      title={comparison.comparison_note || undefined}
    >
      <Icon className="w-3 h-3" />
      {comparison.is_zero_baseline || comparison.percentage_change === null || comparison.percentage_change === undefined ? (
        <span>
          {Number(comparison.absolute_difference) >= 0 ? '+' : ''}
          {formatINR(comparison.absolute_difference)} vs prev
        </span>
      ) : (
        <span>
          {Number(comparison.percentage_change) > 0 ? '+' : ''}
          {comparison.percentage_change}% ({formatINR(comparison.absolute_difference)})
        </span>
      )}
    </span>
  );
};
