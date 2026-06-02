/**
 * Org compliance review operator helpers — shared by queue page and hydrated review modal.
 * Mutations use POST .../compliance-evidence/{id}/verification only (no parallel review API).
 */
import { clientAPI } from '../api/client';
import { pickLatestComplianceEvidenceRecord } from './complianceEvidenceSubmissionView';

export const ORG_REVIEW_OWNER = 'org_admin';
export const ORG_GOVERNANCE_FAMILY = 'ORG_ADMIN_REVIEWED';
export const VERIFICATION_PENDING = 'PENDING_REVIEW';

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function requirementEligibleForOrgOperatorReview(row) {
  if (!row || typeof row !== 'object') return false;
  if (String(row.governance_family || '') !== ORG_GOVERNANCE_FAMILY) return false;
  if (row.queue_backed_review !== true) return false;
  if (String(row.review_owner || '') !== ORG_REVIEW_OWNER) return false;
  return true;
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} latestCer
 */
export function resolveOrgReviewEvidenceRecordId(requirement, latestCer) {
  const fromCer = String(latestCer?.evidence_record_id || '').trim();
  if (fromCer) return fromCer;
  const ea =
    requirement?.evidence_authority && typeof requirement.evidence_authority === 'object'
      ? requirement.evidence_authority
      : {};
  const fromEa = String(ea.primary_evidence_record_id || requirement?.primary_evidence_record_id || '').trim();
  return fromEa || '';
}

/**
 * @param {Record<string, unknown>|null|undefined} cer
 */
export function cerAwaitingOrgVerification(cer) {
  if (!cer || typeof cer !== 'object') return false;
  return String(cer.verification_status || '').toUpperCase() === VERIFICATION_PENDING;
}

/**
 * @param {string} level
 */
export function humanizeEvidenceConfidence(level) {
  const raw = String(level || '').trim().toUpperCase();
  if (!raw) return null;
  if (raw === 'HIGH') {
    return 'High confidence — submission is detailed and consistent; confirm it matches the requirement before verifying.';
  }
  if (raw === 'MEDIUM') {
    return 'Medium confidence — submission appears complete but still requires your review.';
  }
  if (raw === 'LOW') {
    return 'Low confidence — key details may be missing; check carefully before accepting.';
  }
  return `Confidence (${raw.toLowerCase()}) — review the submission before deciding.`;
}

/**
 * @param {Record<string, unknown>|null|undefined} merged
 * @param {Record<string, unknown>|null|undefined} cer
 */
export function buildOperatorReviewContextSummary(merged, cer) {
  const truth = String(merged?.truth_presentation_label || merged?.truth_presentation_stage || '').trim();
  const stage = String(merged?.truth_presentation_stage || '').toLowerCase();
  let reviewStatus = 'Pending organisation review';
  if (stage === 'org_verification_pending' || truth.toLowerCase().includes('organisation')) {
    reviewStatus = 'Awaiting organisation verification';
  } else if (truth) {
    reviewStatus = truth;
  }

  const submittedAt = cer?.created_at || merged?.evidence_last_submitted_at || merged?.updated_at;
  const submittedBy = cer?.created_by_user_id || cer?.created_by || null;
  const mode = String(cer?.evidence_mode || '').trim();

  return {
    reviewStatus,
    submittedAt,
    submittedBy: submittedBy ? String(submittedBy) : null,
    evidenceType: mode ? mode.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) : null,
    confidenceLevel: cer?.evidence_confidence_level ? String(cer.evidence_confidence_level) : null,
    verificationStatus: cer?.verification_status ? String(cer.verification_status) : null,
  };
}

export const OPERATOR_REVIEW_GUIDANCE = {
  inspect:
    'Review the structured submission below. Confirm it matches this property and requirement before you verify or reject.',
  verify: 'Verify accepts the submission and updates compliance status for this property.',
  reject: 'Reject sends the requirement back for correction; the submitter may need to submit again.',
};

/**
 * @param {{
 *   propertyId: string,
 *   requirementId: string,
 *   evidenceRecordId: string,
 *   decision: 'VERIFY' | 'REJECT',
 * }} args
 */
export async function submitOrgComplianceEvidenceVerification({ propertyId, requirementId, evidenceRecordId, decision }) {
  return clientAPI.postComplianceEvidenceVerification(propertyId, requirementId, evidenceRecordId, { decision });
}

/**
 * @param {Array<Record<string, unknown>>|null|undefined} records
 */
export function pickPendingOrgReviewCer(records) {
  const latest = pickLatestComplianceEvidenceRecord(records);
  if (latest && cerAwaitingOrgVerification(latest)) return latest;
  if (!Array.isArray(records)) return null;
  for (const rec of records) {
    if (rec && cerAwaitingOrgVerification(rec)) return rec;
  }
  return latest;
}
