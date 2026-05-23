import React from 'react';
import { formatMinorUnits } from '../../utils/rentMoney';

const CARDS = [
  { key: 'collected', label: 'Collected this month', field: 'rent_collected_this_month_minor', format: 'money', filter: { status: 'PAID' } },
  { key: 'upcoming', label: 'Upcoming due', field: 'upcoming_due_count', format: 'count', filter: { status: 'UPCOMING' } },
  { key: 'overdue', label: 'Overdue', field: 'overdue_count', format: 'count', filter: { attention_only: true, overdue_only: true } },
  { key: 'partial', label: 'Partially paid', field: 'partially_paid_count', format: 'count', filter: { status: 'PARTIALLY_PAID' } },
  { key: 'arrears', label: 'Properties in arrears', field: 'tenancies_with_arrears_count', format: 'count', filter: { attention_only: true } },
  { key: 'delay', label: 'Avg payment delay', field: 'average_payment_delay_days', format: 'days', filter: {} },
];

export function RentSummaryCards({ summary, activeFilter, onFilter }) {
  if (!summary) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6" data-testid="rent-summary-cards">
      {CARDS.map((card) => {
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
        return (
          <button
            key={card.key}
            type="button"
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
          </button>
        );
      })}
    </div>
  );
}
