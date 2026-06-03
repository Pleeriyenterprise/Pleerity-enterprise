/**
 * Client-visible compliance headline display aligned with SCORING_SEMANTICS_V1.
 * Do not show a numeric 0–100 headline unless the backend exposes an authoritative numeric score
 * for a status that permits display (ok, partial, stale).
 */

export const SCORING_HEADLINE_NO_DATA = 'No data yet';

const BLOCKED_NUMERIC = new Set(['unavailable', 'reconciliation_required', 'unknown']);

/**
 * @param {unknown} score
 * @param {string | undefined | null} scoreStatus
 * @returns {number|string}
 */
export function headlineScoreDisplayForDashboard(score, scoreStatus) {
  const st = scoreStatus || '';
  if (BLOCKED_NUMERIC.has(st)) return SCORING_HEADLINE_NO_DATA;
  if (st === 'calculating') return 'Updating…';
  if (score == null || score === '' || (typeof score === 'number' && Number.isNaN(score))) {
    return SCORING_HEADLINE_NO_DATA;
  }
  if (typeof score === 'number') return score;
  const n = Number(score);
  return Number.isNaN(n) ? SCORING_HEADLINE_NO_DATA : Math.round(n);
}

/**
 * True only when the UI may append "/100" to the headline.
 * @param {unknown} score
 * @param {string | undefined | null} scoreStatus
 */
export function headlineScoreShowsOutOf100(score, scoreStatus) {
  const d = headlineScoreDisplayForDashboard(score, scoreStatus);
  return typeof d === 'number' && !Number.isNaN(d);
}
