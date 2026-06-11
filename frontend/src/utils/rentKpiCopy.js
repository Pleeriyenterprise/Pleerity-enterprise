/**
 * Rent Operations KPI labels, helpers, and filter metadata.
 */

export const RENT_KPI_CARDS = [
  {
    key: 'collected',
    label: 'Collected this month',
    field: 'rent_collected_this_month_minor',
    format: 'money',
    filter: {},
    metricOnly: true,
    helper: 'Payments recorded with a payment date in the current month.',
    emptyHelper: 'No rent payments recorded this month.',
  },
  {
    key: 'upcoming',
    label: 'Upcoming periods',
    field: 'upcoming_due_count',
    format: 'count',
    filter: { status: 'UPCOMING' },
    helper: 'Rent periods due in the future.',
  },
  {
    key: 'overdue',
    label: 'Overdue',
    field: 'overdue_count',
    format: 'count',
    filter: { attention_only: true, overdue_only: true },
    helper: 'Rent periods past due with an outstanding balance.',
  },
  {
    key: 'partial',
    label: 'Partially paid',
    field: 'partially_paid_count',
    format: 'count',
    filter: { status: 'PARTIALLY_PAID' },
    helper: 'Rent periods with a recorded payment but balance still outstanding.',
  },
  {
    key: 'arrears',
    label: 'Tenancies in arrears',
    field: 'tenancies_with_arrears_count',
    format: 'count',
    filter: { attention_only: true },
    helper: 'Distinct tenancies or properties with overdue or partial balances.',
  },
  {
    key: 'delay',
    label: 'Avg late payment',
    field: 'average_payment_delay_days',
    format: 'days',
    filter: {},
    metricOnly: true,
    helper: 'Average days late among paid periods only.',
    emptyHelper: 'No late paid periods yet.',
  },
];

/** @param {typeof RENT_KPI_CARDS[number]|null|undefined} card */
export function rentKpiCompatibleWithTab(card, tab) {
  if (!card || tab === 'expenses' || card.metricOnly) return false;
  if (tab === 'attention') return Boolean(card.filter?.attention_only);
  if (tab === 'ledger') return Boolean(card.filter?.status);
  return false;
}

/** @param {typeof RENT_KPI_CARDS[number]} card */
export function rentKpiTargetTab(card) {
  if (card.metricOnly) return null;
  if (card.filter?.attention_only || card.filter?.overdue_only) return 'attention';
  if (card.filter?.status) return 'ledger';
  return null;
}

export function rentListCountHint(visibleCount, totalCount) {
  const visible = Number(visibleCount) || 0;
  const total = Number(totalCount) || 0;
  if (total <= visible) return null;
  return `Showing ${visible} of ${total} periods`;
}
