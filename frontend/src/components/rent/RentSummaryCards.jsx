import React from 'react';
import { formatMinorUnits } from '../../utils/rentMoney';
import { RENT_KPI_CARDS } from '../../utils/rentKpiCopy';

export function RentSummaryCards({ summary, activeFilter, onFilter }) {
  if (!summary) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6" data-testid="rent-summary-cards">
      {RENT_KPI_CARDS.map((card) => {
        const raw = summary[card.field];
        const display =
          card.format === 'money'
            ? formatMinorUnits(raw, summary.currency)
            : card.format === 'days'
              ? raw > 0
                ? `${raw}d`
                : '—'
              : String(raw ?? 0);
        const isActive = activeFilter?.key === card.key;
        const isEmpty =
          (card.format === 'money' && !(raw > 0)) ||
          (card.format === 'days' && !(raw > 0));
        const title = [card.helper, isEmpty && card.emptyHelper ? card.emptyHelper : null]
          .filter(Boolean)
          .join(' ');

        return (
          <button
            key={card.key}
            type="button"
            title={title}
            onClick={() => onFilter(card)}
            className={`rounded-lg border p-3 text-left transition-colors ${
              isActive ? 'border-electric-teal bg-teal-50/50' : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
            data-testid={`rent-kpi-${card.key}`}
          >
            <p className="text-xs text-gray-500 uppercase tracking-wide">{card.label}</p>
            <p
              className={`text-lg font-semibold ${
                card.key === 'overdue' || card.key === 'arrears' ? 'text-orange-600' : 'text-midnight-blue'
              }`}
            >
              {display}
            </p>
            {isEmpty && card.emptyHelper ? (
              <p className="text-[10px] text-gray-500 mt-1 leading-snug">{card.emptyHelper}</p>
            ) : card.helper ? (
              <p className="text-[10px] text-gray-500 mt-1 leading-snug line-clamp-2">{card.helper}</p>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
