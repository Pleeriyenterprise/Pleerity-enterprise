/**
 * Shared copy/helpers for portfolio compliance headline freshness (Stream B async honesty).
 * No API changes — consumes existing score_status / score_status_message / timestamps.
 */

/** Client-visible non-ok headline states (aligned with scoring_semantics_v1). */
export const DASHBOARD_NON_OK_SCORE_STATUSES = new Set([
  'calculating',
  'partial',
  'stale',
  'reconciliation_required',
  'unavailable',
  'unknown',
]);

/** When score_status is calculating and the API omits score_status_message. */
export const CALCULATING_SCORE_FALLBACK_MESSAGE =
  'Your latest changes are saved. The portfolio score updates after the next background calculation.';

const DEFAULT_EXPLANATION_WHEN_NO_SERVER_MESSAGE = {
  reconciliation_required:
    'Persisted compliance scores are not yet available for every property. The headline will update after the next calculation.',
  unavailable: 'Compliance score is not available for this view.',
  unknown: 'Compliance score status is unclear. Try refreshing in a moment.',
};

/**
 * @param {string | null | undefined} status
 * @returns {boolean}
 */
export function isNonOkDashboardScoreStatus(status) {
  const s = String(status || '')
    .trim()
    .toLowerCase();
  return DASHBOARD_NON_OK_SCORE_STATUSES.has(s);
}

/**
 * Prefer portfolio_last_calculated_at for portfolio wording; falls back to last_calculated_at / score_last_calculated_at.
 * @param {Record<string, unknown> | null | undefined} payload
 * @returns {string | null} ISO or raw string timestamp, or null
 */
export function pickScoreLastCalculatedIso(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const a = payload.portfolio_last_calculated_at;
  const b = payload.last_calculated_at;
  const c = payload.score_last_calculated_at;
  const pick = a ?? b ?? c;
  if (pick == null || pick === '') return null;
  return String(pick);
}

/**
 * One-line explanation for non-ok headline status (dashboard / cards).
 * @param {string | null | undefined} scoreStatus
 * @param {string | null | undefined} scoreStatusMessage
 * @returns {string | null}
 */
export function resolveDashboardFreshnessExplanation(scoreStatus, scoreStatusMessage) {
  const st = String(scoreStatus || '')
    .trim()
    .toLowerCase();
  if (!isNonOkDashboardScoreStatus(st)) return null;
  const trimmedMsg = scoreStatusMessage != null ? String(scoreStatusMessage).trim() : '';
  if (trimmedMsg) return trimmedMsg;
  if (st === 'calculating') return CALCULATING_SCORE_FALLBACK_MESSAGE;
  const fallback = DEFAULT_EXPLANATION_WHEN_NO_SERVER_MESSAGE[st];
  return fallback || null;
}

/**
 * Human-readable line for “when stored scores were last calculated” (factual, not alarming).
 * @param {string | null | undefined} isoOrString
 * @returns {string | null}
 */
export function formatScoreLastCalculatedForUi(isoOrString) {
  if (!isoOrString || typeof isoOrString !== 'string') return null;
  try {
    const d = new Date(isoOrString);
    if (Number.isNaN(d.getTime())) return `Last calculated: ${isoOrString}`;
    return `Portfolio scores last calculated: ${d.toLocaleString()}`;
  } catch {
    return `Last calculated: ${isoOrString}`;
  }
}

/** Short note for score drivers vs headline (Compliance score page). */
export const COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE =
  'These rows reflect your requirements right now. The headline score may update shortly after you make changes.';

/**
 * Server-backed note when one or more properties have `compliance_score_pending` (recalc queued).
 * @param {Record<string, unknown> | null | undefined} payload compliance-score API body or dashboard headline object
 * @returns {string | null}
 */
export function portfolioScoreRecalcPendingNote(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const raw = payload.portfolio_score_recalc_pending_note;
  if (raw == null || String(raw).trim() === '') return null;
  return String(raw).trim();
}

/** Clarifies document KPIs on the compliance score page (upload vs accepted). */
export const COMPLIANCE_SCORE_DOCUMENTS_UPLOAD_VS_VERIFIED_NOTE =
  'Upload counts include any file on record. Accepted coverage counts documents that have passed review or verification — uploads alone may not count until accepted.';

/** Command Centre when `compliance_status_summary` is missing from the bundle (partial load). */
export const COMMAND_CENTER_COMPLIANCE_SNAPSHOT_UNAVAILABLE =
  'Compliance snapshot could not be loaded in this bundle. Other sections may still be current; refresh or open Dashboard for the full score.';

/** Property Detail when stored headline and explainability / operational preview are both shown. */
export const PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE =
  'The headline uses the latest stored property score. Detail panels may include current requirement data while recalculation is pending.';

/** PVG-004 Work queue: compliance headline snapshot failed (network/API); not a processing state. */
export const WORK_QUEUE_SCORE_SNAPSHOT_LOAD_FAILED =
  'We could not load your portfolio score context. Refresh the page or try again in a moment.';

/**
 * PVG-004: Headline states where the score may not update predictably or needs follow-up (distinct from “still calculating”).
 * @param {string | null | undefined} scoreStatus
 * @returns {boolean}
 */
export function isWorkQueueScoreHeadlineDegradedStatus(scoreStatus) {
  const s = String(scoreStatus || '')
    .trim()
    .toLowerCase();
  return s === 'unavailable' || s === 'unknown' || s === 'reconciliation_required';
}
