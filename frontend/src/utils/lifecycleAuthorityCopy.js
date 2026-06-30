/**
 * Lifecycle authority presentation copy (PRESENTATION-AUTHORITY-ALIGNMENT-01).
 * Mirror: backend/services/lifecycle_authority_copy.py
 *
 * Does not derive lifecycle state — only governed customer-facing phrases.
 */

export const CALENDAR_OVERDUE_SUBLINE =
  'Past effective expiry — renew or confirm dates. This reflects your certificate calendar, not a legal compliance verdict.';

export const EVIDENCE_REQUIRED_LABEL = 'Evidence required';
export const AWAITING_VERIFICATION_LABEL = 'Awaiting verification';

export const COUNT_SEMANTICS_EXPLANATION =
  'Some identified obligations are informational, conditional, jurisdiction-specific, archived, or otherwise outside active operational tracking. Nothing has been removed.';

export const RECOMMENDATION_LENS = {
  onboarding: 'Onboarding checklist',
  operational: 'Operational inbox (Today)',
  triage: 'Portfolio triage (Command Centre)',
  kpi: 'Compliance score recommendations',
};

/**
 * Subline for calendar OVERDUE/EXPIRED when lifecycle fields are absent (legacy path).
 * @param {object|null|undefined} row
 */
export function calendarOverdueSubline(row) {
  const lc = String(row?.client_lifecycle_state || '').toUpperCase();
  if (lc === 'PENDING_REVIEW') {
    return 'Awaiting platform verification — calendar date may still need confirmation.';
  }
  return CALENDAR_OVERDUE_SUBLINE;
}

/**
 * Risk signal headline must not imply legal breach when backend category is operational/predictive.
 * @param {{ risk_type?: string, risk_type_label_client?: string, category?: string }} signal
 */
export function riskSignalPresentationHeadline(signal) {
  const label = String(signal?.risk_type_label_client || '').trim();
  if (label) return label;
  const cat = String(signal?.category || '').toLowerCase();
  const rt = String(signal?.risk_type || '').toLowerCase();
  if (cat === 'compliance' && rt.includes('electrical')) {
    return 'Electrical certificate attention';
  }
  if (cat === 'asset') return 'Property maintenance pattern';
  if (cat === 'operational') return 'Operational follow-up suggested';
  return 'Review suggested';
}
