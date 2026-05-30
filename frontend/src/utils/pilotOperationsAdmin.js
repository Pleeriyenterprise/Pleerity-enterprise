/**
 * Founding pilot operations — client-side filters/metrics (backend remains authoritative).
 */

export const HEALTH_BANDS = ['healthy', 'at_risk', 'inactive', 'conversion_ready'];

export const GOVERNANCE_STATUSES = [
  'active',
  'extended',
  'expired',
  'converted',
  'cancelled',
  'comped',
  'paused',
];

export const BILLING_STATUSES = ['trialing', 'active', 'past_due', 'unpaid', 'cancelled', 'incomplete', 'none'];

export const ENTITLEMENT_STATUSES = ['enabled', 'suspended', 'revoked', 'grace_period'];

export function accountDisplayName(row) {
  return row?.full_name || row?.contact_email || row?.email || row?.client_id || '—';
}

export function accountEmail(row) {
  return row?.contact_email || row?.email || '—';
}

export function flattenAccountRow(row) {
  const ops = row?.ops || {};
  const domains = ops?.lifecycle_domains || {};
  const risk = row?.pilot_conversion_risk || ops?.conversion_readiness || {};
  return {
    client_id: row?.client_id,
    name: accountDisplayName(row),
    email: accountEmail(row),
    billing_plan: row?.billing_plan || '—',
    pilot_status: row?.pilot_status,
    governance: ops?.pilot_governance_status || domains?.pilot_governance_status || row?.pilot_governance_status,
    billing: ops?.pilot_billing_status || domains?.pilot_billing_status || row?.pilot_billing_status,
    entitlement: ops?.pilot_entitlement_status || domains?.pilot_entitlement_status || row?.pilot_entitlement_status,
    health_band: ops?.pilot_health_band || row?.pilot_health_band,
    health_score: ops?.pilot_health_score ?? row?.pilot_health_score,
    days_remaining: ops?.days_remaining,
    expected_paid: row?.pilot_expected_first_paid_invoice_at || ops?.effective_expires_at,
    payment_method_collected: ops?.payment_method_collected ?? row?.pilot_stripe_payment_method_collected,
    onboarding_fee_policy: row?.onboarding_fee_policy,
    invite_code: row?.pilot_invite_code,
    anomaly_count: (row?.open_anomalies || []).length,
    is_comped: (ops?.pilot_governance_status || row?.pilot_status) === 'comped',
    likely_conversion: risk?.likely_conversion,
    missing_payment_method: risk?.missing_payment_method ?? ops?.conversion_readiness?.missing_payment_method,
    likely_churn: risk?.likely_churn,
    approaching_paid: risk?.approaching_paid_transition ?? ops?.conversion_readiness?.approaching_paid_transition,
    health_flags: ops?.pilot_health_flags || row?.pilot_health_flags || [],
    cancellation_risk: ops?.cancellation_risk,
    _raw: row,
  };
}

export function computeOpsMetrics(accounts) {
  const rows = (accounts || []).map(flattenAccountRow);
  const m = {
    total: rows.length,
    active: 0,
    nearing_expiry: 0,
    converted: 0,
    cancelled_before_conversion: 0,
    missing_payment_method: 0,
    open_anomalies: 0,
    at_risk: 0,
    healthy: 0,
    conversion_ready: 0,
    comped: 0,
    with_anomalies: 0,
  };
  for (const r of rows) {
    const gov = (r.governance || r.pilot_status || '').toLowerCase();
    if (gov === 'active' || gov === 'extended') m.active += 1;
    if (r.days_remaining != null && r.days_remaining <= 14 && r.days_remaining >= 0) m.nearing_expiry += 1;
    if (gov === 'converted' || r.pilot_status === 'converted_to_paid') m.converted += 1;
    if (r._raw?.pilot_cancelled_before_paid_conversion || r.likely_churn) m.cancelled_before_conversion += 1;
    if (r.missing_payment_method) m.missing_payment_method += 1;
    m.open_anomalies += r.anomaly_count;
    if (r.anomaly_count > 0) m.with_anomalies += 1;
    if (r.health_band === 'at_risk') m.at_risk += 1;
    if (r.health_band === 'healthy') m.healthy += 1;
    if (r.health_band === 'conversion_ready') m.conversion_ready += 1;
    if (r.is_comped) m.comped += 1;
  }
  return m;
}

export function filterPilotAccounts(accounts, filters, search) {
  let rows = (accounts || []).map(flattenAccountRow);
  const q = (search || '').trim().toLowerCase();
  if (q) {
    rows = rows.filter(
      (r) =>
        r.client_id?.toLowerCase().includes(q) ||
        r.name?.toLowerCase().includes(q) ||
        r.email?.toLowerCase().includes(q) ||
        r.invite_code?.toLowerCase().includes(q),
    );
  }
  const f = filters || {};
  if (f.governance) {
    rows = rows.filter((r) => (r.governance || r.pilot_status || '').toLowerCase() === f.governance);
  }
  if (f.billing) rows = rows.filter((r) => (r.billing || '').toLowerCase() === f.billing);
  if (f.entitlement) rows = rows.filter((r) => (r.entitlement || '').toLowerCase() === f.entitlement);
  if (f.health_band) rows = rows.filter((r) => r.health_band === f.health_band);
  if (f.conversion_ready) rows = rows.filter((r) => r.likely_conversion || r.health_band === 'conversion_ready');
  if (f.missing_pm) rows = rows.filter((r) => r.missing_payment_method);
  if (f.has_anomalies) rows = rows.filter((r) => r.anomaly_count > 0);
  if (f.nearing_expiry) {
    rows = rows.filter((r) => r.days_remaining != null && r.days_remaining <= 14);
  }
  if (f.converted) {
    rows = rows.filter((r) => {
      const g = (r.governance || '').toLowerCase();
      return g === 'converted' || r.pilot_status === 'converted_to_paid';
    });
  }
  if (f.comped) rows = rows.filter((r) => r.is_comped);
  if (f.inactive) rows = rows.filter((r) => r.health_band === 'inactive');
  return rows;
}

export function sortPilotAccounts(rows, sortKey, sortDir) {
  const dir = sortDir === 'asc' ? 1 : -1;
  const copy = [...rows];
  copy.sort((a, b) => {
    let av = a[sortKey];
    let bv = b[sortKey];
    if (sortKey === 'name') {
      av = a.name;
      bv = b.name;
    }
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
    return String(av).localeCompare(String(bv)) * dir;
  });
  return copy;
}

export function healthBandClass(band) {
  const b = (band || '').toLowerCase();
  if (b === 'healthy') return 'bg-emerald-100 text-emerald-800';
  if (b === 'conversion_ready') return 'bg-teal-100 text-teal-900';
  if (b === 'at_risk') return 'bg-amber-100 text-amber-900';
  if (b === 'inactive') return 'bg-slate-200 text-slate-700';
  return 'bg-gray-100 text-gray-700';
}

export function severityClass(severity) {
  const s = (severity || '').toLowerCase();
  if (s === 'critical') return 'bg-red-100 text-red-800';
  if (s === 'warning') return 'bg-amber-100 text-amber-900';
  return 'bg-slate-100 text-slate-700';
}

const TIMELINE_LABELS = {
  created: 'Pilot activated',
  extended: 'Pilot extended',
  shortened: 'Pilot shortened',
  expiry_set: 'Expiry updated',
  cancelled: 'Pilot cancelled',
  converted_to_paid: 'Converted to paid',
  comped: 'Comped access granted',
  paused: 'Pilot paused',
  resumed: 'Pilot resumed',
  expired: 'Pilot expired',
  stripe_paid_transition: 'Stripe paid transition',
  stripe_cancelled_before_paid: 'Cancelled before paid conversion',
  notes_updated: 'Notes updated',
  operational_reconcile_warning: 'Reconciliation warning',
};

const TIMELINE_CATEGORY = {
  created: 'activation',
  extended: 'governance',
  expiry_set: 'governance',
  cancelled: 'governance',
  converted_to_paid: 'conversion',
  comped: 'governance',
  paused: 'governance',
  resumed: 'governance',
  expired: 'governance',
  stripe_paid_transition: 'billing',
  stripe_cancelled_before_paid: 'billing',
  operational_reconcile_warning: 'reconciliation',
};

export function formatTimelineEvent(ev) {
  const action = ev?.action_type || 'event';
  return {
    id: ev?.audit_id || action,
    label: TIMELINE_LABELS[action] || action.replace(/_/g, ' '),
    category: TIMELINE_CATEGORY[action] || 'governance',
    timestamp: ev?.created_at,
    actor: ev?.actor,
    reason: ev?.reason,
    notes: ev?.notes,
    raw: ev,
  };
}

export { apiErrorMessage, formatApiDetail, formatDisplayValue } from './apiErrorMessage';
