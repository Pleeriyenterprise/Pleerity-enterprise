/**
 * Lifecycle KPI attention breakdown (P5-S4/P5-S5).
 * Additive API field — does not replace monolithic expiring_soon tile.
 */

export const LIFECYCLE_KPI_BREAKDOWN_ORDER = [
  'certificate_expiring',
  'review_due',
  'event_action_required',
  'tenancy_term_ending',
  'occupancy_review_due',
  'operational_action_required',
];

/** Display labels for dashboard strip only (not global presentation language). */
export const LIFECYCLE_KPI_BREAKDOWN_LABELS = {
  certificate_expiring: 'Certificate expiring',
  review_due: 'Review due',
  event_action_required: 'Event action required',
  tenancy_term_ending: 'Tenancy term ending',
  occupancy_review_due: 'Occupancy review due',
  operational_action_required: 'Operational action required',
};

export function lifecycleKpiBreakdownFromStats(stats) {
  const raw = stats?.lifecycle_kpi_breakdown;
  if (!raw || typeof raw !== 'object') return null;
  return raw;
}

export function hasLifecycleKpiBreakdown(stats) {
  const breakdown = lifecycleKpiBreakdownFromStats(stats);
  if (!breakdown) return false;
  return LIFECYCLE_KPI_BREAKDOWN_ORDER.some((key) => Number(breakdown[key] || 0) > 0);
}

export function lifecycleKpiBreakdownEntries(stats) {
  const breakdown = lifecycleKpiBreakdownFromStats(stats);
  if (!breakdown) return [];
  return LIFECYCLE_KPI_BREAKDOWN_ORDER.map((key) => ({
    key,
    label: LIFECYCLE_KPI_BREAKDOWN_LABELS[key] || key,
    count: Number(breakdown[key] || 0),
  })).filter((row) => row.count > 0);
}

export function lifecycleKpiEffectiveMode(stats) {
  const mode = stats?.lifecycle_kpi_effective_mode;
  return typeof mode === 'string' ? mode : null;
}
