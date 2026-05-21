/**
 * Bounded right-to-rent mixed-evidence trust presentation (OPS-VERIFY-01).
 * Presentation-only: does not change authority, queues, or review outcomes.
 */
import {
  isSubmissionAwaitingReview,
  requirementHasPersistedClientSubmission,
} from './clientPersistedSubmissionPresentation';
import { normalizeWorkflowClass } from './workflowSemantics';

const RTR_CODES = new Set(['right_to_rent', 'right_to_rent_checks']);

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function isRightToRentRequirement(row) {
  const code = String(
    row?.requirement_code || row?.requirement_type || row?.canonical_requirement_code || '',
  )
    .trim()
    .toLowerCase();
  return RTR_CODES.has(code);
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function evidenceAuthorityState(row) {
  const ea = row?.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  return String(ea?.state || '').trim().toUpperCase();
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function authorityPermitsVerifiedPresentationLanguage(row) {
  const st = evidenceAuthorityState(row);
  return st === 'VERIFIED_CURRENT' || st === 'VERIFIED';
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function isGuidedDeclarationPrimaryWorkflow(row) {
  if (isRightToRentRequirement(row)) return true;
  const wf = normalizeWorkflowClass(row?.workflow_class);
  if (wf === 'GUIDED_DECLARATION') return true;
  const meta =
    row?.registry_metadata && typeof row.registry_metadata === 'object' ? row.registry_metadata : null;
  const er = meta?.evidence_resolution && typeof meta.evidence_resolution === 'object' ? meta.evidence_resolution : null;
  return String(er?.primary_resolution_workflow || '').trim().toUpperCase() === 'GUIDED_DECLARATION';
}

/**
 * Document and/or CER on file, guided-declaration RTR, authority not terminal-verified.
 * @param {Record<string, unknown>|null|undefined} row
 */
export function isRightToRentMixedEvidencePendingReview(row) {
  if (!row || typeof row !== 'object') return false;
  if (!isRightToRentRequirement(row)) return false;
  if (!isGuidedDeclarationPrimaryWorkflow(row)) return false;
  if (!requirementHasPersistedClientSubmission(row)) return false;
  if (authorityPermitsVerifiedPresentationLanguage(row)) return false;
  const ea = evidenceAuthorityState(row);
  if (ea === 'UPLOADED_UNCONFIRMED' || ea === 'PENDING_ADMIN_REVIEW') return true;
  // Portfolio matrix rows may omit evidence_authority while still linking a document.
  if (!ea && (row.evidence_doc_id || row.document_id)) {
    const st = String(row.status || '').trim().toUpperCase();
    if (st === 'PENDING' || st === 'VALID' || st === 'EXPIRING_SOON') return true;
  }
  return isSubmissionAwaitingReview(row);
}

export function rightToRentPendingReviewEvidenceLine() {
  return 'Check record on file — awaiting review';
}

export function rightToRentPendingReviewComplianceLine() {
  return 'Evidence submitted — awaiting review';
}

export function guidedMixedEvidenceInitialMode() {
  return 'STRUCTURED_DECLARATION';
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @param {Record<string, unknown>|null|undefined} ta
 */
export function shouldPreferGuidedEvidenceOverIntelView(row, ta) {
  if (!isRightToRentMixedEvidencePendingReview(row)) return false;
  return String(ta?.primary_action_handler || '') === 'guided_evidence';
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} cta
 * @returns {Record<string, unknown>|null}
 */
export function resolveRightToRentMixedEvidenceCtaPresentation(requirement, cta) {
  if (!cta || typeof cta !== 'object') return null;
  if (!isRightToRentMixedEvidencePendingReview(requirement)) return null;
  if (String(cta.primary_action_handler || '') !== 'guided_evidence') return null;

  const primary_action_label = requirementHasPersistedClientSubmission(requirement)
    ? 'Record updated check'
    : 'Update check record';

  let secondary_action = cta.secondary_action;
  if (secondary_action && typeof secondary_action === 'object') {
    const secLabel = String(secondary_action.label || '');
    if (/^upload\b/i.test(secLabel) && !/additional/i.test(secLabel)) {
      secondary_action = { ...secondary_action, label: 'Upload additional evidence' };
    }
  }

  return {
    ...cta,
    primary_action_label,
    secondary_action,
    guided_initial_evidence_mode: guidedMixedEvidenceInitialMode(),
  };
}
