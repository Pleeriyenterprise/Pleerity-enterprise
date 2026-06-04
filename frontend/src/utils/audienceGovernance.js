/**
 * AUDIENCE-GOVERNANCE-CONVERGENCE-01 — landlord operational interpretation (API mirror).
 * Prefer API `audience_interpretation` on enriched requirements when present.
 */

export const AUDIENCE_LANDLORD_OPERATIONAL = 'LANDLORD_OPERATIONAL';

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {Record<string, unknown>|null}
 */
export function landlordAudienceInterpretation(row) {
  const interp = row?.audience_interpretation;
  if (interp && typeof interp === 'object') return interp;
  return null;
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {string}
 */
export function landlordAudienceStatusLabel(row) {
  const interp = landlordAudienceInterpretation(row);
  if (interp?.audience_status_label) return String(interp.audience_status_label);
  return '';
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {boolean}
 */
export function landlordShowsNoImmediateAction(row) {
  const interp = landlordAudienceInterpretation(row);
  return interp?.action_visibility === 'none' && interp?.landlord_next_action?.includes('No immediate');
}
