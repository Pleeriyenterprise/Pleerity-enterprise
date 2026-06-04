/**
 * REPORTING-HUMAN-LANGUAGE-CONVERGENCE-01 — customer-facing report/export labels.
 * Mirrors backend services/report_human_language_v1.py for UI surfaces.
 */

export const SCORE_STATUS_LABELS = {
  calculating: 'Score updating',
  partial: 'Partially calculated',
  stale: 'Score may be out of date',
  ok: 'Current',
  reconciliation_required: 'Reconciliation in progress',
  unavailable: 'Not available',
  unknown: 'Status unclear',
  pending_recalc: 'Score updating',
};

export const LIFECYCLE_LABELS = {
  ACTION_REQUIRED: 'Action required',
  PENDING_REVIEW: 'Awaiting review',
  SATISFIED_UNVERIFIED: 'Recorded on file',
  VERIFIED: 'Verified',
  NOT_APPLICABLE: 'Not applicable',
};

export const ASSURANCE_TIER_LABELS = {
  SELF_RECORDED: 'Self-recorded assurance',
  PLATFORM_REVIEWED: 'Awaiting review',
  VERIFIED_DOCUMENT: 'Document verified',
};

export const LIVE_EXPORT_DISCLOSURE =
  'This export reflects the latest portfolio information and may differ from previous downloads.';

export const IMMUTABLE_ARTIFACT_DISCLOSURE =
  'Frozen governance record — re-download returns the same file bytes as at generation.';

/**
 * @param {string | null | undefined} scoreStatus
 * @returns {string}
 */
export function humanScoreStatusLabel(scoreStatus) {
  const s = String(scoreStatus || '')
    .trim()
    .toLowerCase();
  if (!s) return '—';
  return SCORE_STATUS_LABELS[s] || '—';
}

/**
 * @param {string | null | undefined} lifecycleState
 * @returns {string}
 */
export function humanLifecycleLabel(lifecycleState) {
  const key = String(lifecycleState || '').trim().toUpperCase();
  if (!key) return '—';
  return LIFECYCLE_LABELS[key] || '—';
}

/**
 * @param {string | null | undefined} text
 * @returns {boolean}
 */
export function containsInternalLanguageLeak(text) {
  const t = String(text || '');
  if (!t.trim()) return false;
  return /\b(SATISFIED_UNVERIFIED|VERIFIED_DOCUMENT|SELF_RECORDED|live_regenerated|AUDIT_ARTIFACT|persisted_property_score|score_status=)\b/i.test(
    t
  );
}
