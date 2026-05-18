/**
 * OPS / TRUST-01: frontend presentation when persisted client submission exists but API
 * lifecycle still reads ACTION_REQUIRED / missing-evidence. Does not change backend authority.
 */

import { resolveClientRequirementLifecycle } from './clientRequirementLifecycle';

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function requirementHasPersistedClientSubmission(row) {
  if (!row || typeof row !== 'object') return false;
  const ea = row.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  const primaryId = String(
    ea?.primary_evidence_record_id || row.primary_evidence_record_id || row.latest_evidence_record_id || '',
  ).trim();
  if (primaryId) return true;
  if (String(row.evidence_record_id || '').trim()) return true;
  if (row.evidence_doc_id || String(row.document_id || '').trim()) return true;
  return false;
}

/**
 * Persisted submission still in client/admin review (not verified current).
 * @param {Record<string, unknown>|null|undefined} row
 */
export function isSubmissionAwaitingReview(row) {
  if (!requirementHasPersistedClientSubmission(row)) return false;
  const lc = String(row.client_lifecycle_state || '').trim().toUpperCase();
  if (lc === 'PENDING_REVIEW') return true;
  const ea = row.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  const eaState = String(ea?.state || '').toUpperCase();
  if (eaState === 'PENDING_ADMIN_REVIEW') return true;
  const vs = String(row.verification_status || row.client_evidence_verification_status || '').toUpperCase();
  if (vs === 'PENDING_REVIEW') return true;
  if (lc === 'ACTION_REQUIRED' || eaState === 'MISSING') return true;
  return false;
}

/**
 * Presentation lifecycle for client surfaces (lists, modals, chips).
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {ReturnType<typeof resolveClientRequirementLifecycle>}
 */
export function resolveClientRequirementLifecycleForPresentation(row) {
  const base = resolveClientRequirementLifecycle(row);
  if (!isSubmissionAwaitingReview(row)) return base;
  if (base.state === 'PENDING_REVIEW' || base.state === 'VERIFIED' || base.state === 'SATISFIED_UNVERIFIED') {
    return base;
  }
  return {
    ...base,
    state: 'PENDING_REVIEW',
    label: 'Awaiting review',
    reasonCodes: [...(base.reasonCodes || []), 'FRONTEND_SUBMISSION_ON_FILE'],
    source: 'presentation',
  };
}

/**
 * @param {string|null|undefined} badgeLabel
 * @param {Record<string, unknown>|null|undefined} row
 */
export function resolveSubmissionAwareEvidenceBadgeLabel(badgeLabel, row) {
  const raw = String(badgeLabel || '').trim();
  if (!raw) return null;
  if (!isSubmissionAwaitingReview(row)) return raw;
  if (/^not uploaded$/i.test(raw) || /^no document uploaded$/i.test(raw)) {
    return 'Submission received';
  }
  return raw;
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function submissionAwaitingReviewSubline(row) {
  if (!isSubmissionAwaitingReview(row)) return null;
  return 'Your submission is on file and awaiting review.';
}
