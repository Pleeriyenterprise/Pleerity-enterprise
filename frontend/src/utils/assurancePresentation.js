/**
 * Three-tier assurance presentation (REVIEW-ASSURANCE-SIMPLIFICATION-01).
 */
export const ASSURANCE_SELF_RECORDED = 'SELF_RECORDED';
export const ASSURANCE_PLATFORM_REVIEWED = 'PLATFORM_REVIEWED';
export const ASSURANCE_VERIFIED_DOCUMENT = 'VERIFIED_DOCUMENT';

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function resolveAssuranceTier(row) {
  if (!row || typeof row !== 'object') return ASSURANCE_SELF_RECORDED;
  const fromApi = String(row.assurance_tier || '').trim().toUpperCase();
  if (fromApi === ASSURANCE_SELF_RECORDED || fromApi === ASSURANCE_PLATFORM_REVIEWED || fromApi === ASSURANCE_VERIFIED_DOCUMENT) {
    return fromApi;
  }
  const stage = String(row.truth_presentation_stage || '').toLowerCase();
  const family = String(row.governance_family || '').toUpperCase();
  const owner = String(row.review_owner || '');
  if (family === 'PLATFORM_VERIFIED' || stage === 'platform_verification_pending' || stage === 'verified') {
    if (family === 'PLATFORM_VERIFIED') return ASSURANCE_VERIFIED_DOCUMENT;
  }
  if (
    owner === 'platform_admin' ||
    owner === 'platform_admin_escalation' ||
    stage === 'escalation_review' ||
    stage === 'platform_verification_pending'
  ) {
    return ASSURANCE_PLATFORM_REVIEWED;
  }
  if (family === 'PLATFORM_VERIFIED') return ASSURANCE_VERIFIED_DOCUMENT;
  return ASSURANCE_SELF_RECORDED;
}

/**
 * @param {string} tier
 */
export function assuranceTierSummary(tier) {
  switch (String(tier || '').toUpperCase()) {
    case ASSURANCE_PLATFORM_REVIEWED:
      return {
        title: 'Awaiting platform review',
        guidance:
          'Pleerity will review this submission. You do not need to verify or reject from your organisation account.',
      };
    case ASSURANCE_VERIFIED_DOCUMENT:
      return {
        title: 'Document verification',
        guidance: 'Certificate verification follows the standard document review path.',
      };
    case ASSURANCE_SELF_RECORDED:
    default:
      return {
        title: 'Recorded on file',
        guidance: 'Self-recorded declaration — timestamped and auditable. No organisation reviewer step.',
      };
  }
}
