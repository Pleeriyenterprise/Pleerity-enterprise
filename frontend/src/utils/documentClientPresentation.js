/**
 * Client-facing document row presentation with admin evidence decision precedence.
 *
 * When API provides document_operational_state (canonical backend projection), prefer it
 * to reduce frontend precedence drift. Falls back to local derivation for older payloads.
 *
 * Precedence (highest first):
 * A. Rejected / invalid evidence
 * B. Admin accepted or externally verified evidence
 * C. Pending admin review
 * D. Match resolved — verification still pending
 * E. AI extraction awaiting user confirmation
 * F. Extraction in progress
 * G. Uploaded / unreviewed
 */

import {
  effectiveAssuranceTier,
  effectiveEvidenceReviewState,
  isPositiveEvidenceState,
  reviewStateLabel,
} from './evidenceReviewUi';

/** @type {Record<string, { key: string, label: string, color: string }>} */
const OPERATIONAL_EVIDENCE_BADGE = {
  EVIDENCE_REJECTED: { key: 'REJECTED', label: reviewStateLabel('REJECTED'), color: 'bg-red-100 text-red-800' },
  EXTERNALLY_VERIFIED: { key: 'VERIFIED', label: 'Externally verified', color: 'bg-green-100 text-green-800' },
  EVIDENCE_VERIFIED: { key: 'VERIFIED', label: reviewStateLabel('VERIFIED'), color: 'bg-green-100 text-green-800' },
  EVIDENCE_ACCEPTED_ON_FILE: {
    key: 'ACCEPTED_UNVERIFIED',
    label: reviewStateLabel('ACCEPTED_UNVERIFIED'),
    color: 'bg-teal-100 text-teal-800',
  },
  EVIDENCE_EXPIRED: { key: 'EXPIRED', label: reviewStateLabel('EXPIRED'), color: 'bg-red-100 text-red-800' },
  EVIDENCE_SUPERSEDED: { key: 'SUPERSEDED', label: reviewStateLabel('SUPERSEDED'), color: 'bg-gray-100 text-gray-700' },
  ADMIN_REVIEW_PENDING: {
    key: 'UNDER_REVIEW',
    label: reviewStateLabel('UNDER_REVIEW'),
    color: 'bg-indigo-100 text-indigo-800',
  },
  MATCH_RESOLVED_VERIFICATION_PENDING: {
    key: 'MATCH_PENDING_VERIFY',
    label: 'Requirement linked — verification pending',
    color: 'bg-sky-100 text-sky-900',
  },
  EXTRACTION_CONFIRMATION_PENDING: {
    key: 'EXTRACTION_PENDING',
    label: 'AI data needs review',
    color: 'bg-amber-100 text-amber-800',
  },
  EXTRACTION_IN_PROGRESS: {
    key: 'PROCESSING',
    label: 'Extraction in progress',
    color: 'bg-blue-100 text-blue-800',
  },
  EXTRACTION_FAILED: {
    key: 'EXTRACTION_FAILED',
    label: 'Extraction failed',
    color: 'bg-red-100 text-red-800',
  },
  UPLOADED_AWAITING_REVIEW: {
    key: 'UPLOADED',
    label: reviewStateLabel('UPLOADED'),
    color: 'bg-gray-100 text-gray-700',
  },
};

/** @type {Record<string, { key: string, label: string, color: string }>} */
export const LINKAGE_STATE_BADGE = {
  INTENTIONALLY_UNLINKED: {
    key: 'INTENTIONALLY_UNLINKED',
    label: 'Intentionally unlinked',
    color: 'bg-slate-100 text-slate-700',
  },
  RECONCILIATION_REQUIRED: {
    key: 'RECONCILIATION_REQUIRED',
    label: 'Linkage reconciliation required',
    color: 'bg-orange-100 text-orange-900',
  },
  BROKEN_LINKAGE: {
    key: 'BROKEN_LINKAGE',
    label: 'Broken requirement linkage',
    color: 'bg-red-100 text-red-900',
  },
};

/**
 * @param {Record<string, unknown>} doc
 */
export function linkageReconciliationRequired(doc = {}) {
  if (doc.linkage_reconciliation_required === true) return true;
  const state = String(doc.document_linkage_state || '').toUpperCase();
  return state === 'RECONCILIATION_REQUIRED' || state === 'BROKEN_LINKAGE';
}

/**
 * @param {Record<string, unknown>} doc
 */
export function getClientDocumentLinkageBadge(doc = {}) {
  const state = String(doc.document_linkage_state || '').toUpperCase();
  if (state && LINKAGE_STATE_BADGE[state]) {
    return LINKAGE_STATE_BADGE[state];
  }
  if (doc.document_linkage_label && state && state !== 'LINKED') {
    return { key: state, label: String(doc.document_linkage_label), color: 'bg-gray-100 text-gray-700' };
  }
  return null;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function hasCanonicalOperationalState(doc = {}) {
  return Boolean(String(doc.document_operational_state || '').trim());
}

/**
 * @param {Record<string, unknown>} doc
 */
export function hasAdminSupersededExtractionConfirmation(doc = {}) {
  if (doc.extraction_confirmation_superseded === true) return true;
  const codes = doc.document_operational_reason_codes;
  if (Array.isArray(codes) && codes.includes('EXTRACTION_CONFIRMATION_SUPERSEDED')) {
    return true;
  }
  const ai = doc.ai_extraction;
  if (ai && typeof ai === 'object' && ai.superseded_by_admin_decision) return true;
  return false;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isAdminEvidenceDecisionAccepted(doc = {}) {
  const op = String(doc.document_operational_state || '');
  if (op === 'EVIDENCE_ACCEPTED_ON_FILE' || op === 'EVIDENCE_VERIFIED' || op === 'EXTERNALLY_VERIFIED') {
    return true;
  }
  const review = effectiveEvidenceReviewState(doc);
  if (review === 'REJECTED' || review === 'EXPIRED') return false;
  if (review === 'ACCEPTED_UNVERIFIED' || review === 'VERIFIED') return true;
  const tier = effectiveAssuranceTier(doc);
  if (tier === 'EXTERNALLY_VERIFIED' || tier === 'HUMAN_ACCEPTED') return true;
  const legacy = String(doc.status || '').toUpperCase();
  return legacy === 'VERIFIED';
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isAdminEvidenceDecisionRejected(doc = {}) {
  if (doc.document_operational_state === 'EVIDENCE_REJECTED') return true;
  const review = effectiveEvidenceReviewState(doc);
  if (review === 'REJECTED') return true;
  return String(doc.status || '').toUpperCase() === 'REJECTED';
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isExtractionConfirmationPending(doc = {}) {
  if (hasCanonicalOperationalState(doc)) {
    return doc.document_operational_state === 'EXTRACTION_CONFIRMATION_PENDING';
  }
  if (isAdminEvidenceDecisionAccepted(doc) || isAdminEvidenceDecisionRejected(doc)) {
    return false;
  }
  if (hasAdminSupersededExtractionConfirmation(doc)) {
    return false;
  }
  const rs = String(doc.ai_extraction?.review_status || '').toLowerCase();
  if (rs === 'approved' || rs === 'rejected') {
    return false;
  }
  const extractionStatus = String(doc.extraction_status || '').toUpperCase();
  if (extractionStatus === 'CONFIRMED' || extractionStatus === 'REJECTED') {
    return false;
  }
  if (extractionStatus === 'EXTRACTED' || extractionStatus === 'NEEDS_REVIEW') {
    return true;
  }
  const reviewStatus = String(doc.ai_extraction?.review_status || '').toUpperCase();
  if (!reviewStatus || reviewStatus === 'PENDING' || reviewStatus === 'AWAITING_USER_CONFIRM') {
    const hasAiData = doc.ai_extraction?.status === 'completed' && doc.ai_extraction?.data;
    return Boolean(hasAiData || doc.extraction_id);
  }
  return false;
}

/**
 * Primary evidence status badge for client document lists.
 * @param {Record<string, unknown>} doc
 */
export function getClientDocumentEvidenceBadge(doc = {}) {
  const op = String(doc.document_operational_state || '');
  if (op && OPERATIONAL_EVIDENCE_BADGE[op]) {
    return OPERATIONAL_EVIDENCE_BADGE[op];
  }
  if (doc.document_operational_label && op) {
    return { key: op, label: String(doc.document_operational_label), color: 'bg-gray-100 text-gray-700' };
  }

  if (isAdminEvidenceDecisionRejected(doc)) {
    return { label: reviewStateLabel('REJECTED'), color: 'bg-red-100 text-red-800', key: 'REJECTED' };
  }
  if (String(doc.assurance_tier || '').toUpperCase() === 'EXTERNALLY_VERIFIED') {
    return { label: 'Externally verified', color: 'bg-green-100 text-green-800', key: 'VERIFIED' };
  }
  const review = effectiveEvidenceReviewState(doc);
  if (review === 'ACCEPTED_UNVERIFIED') {
    return {
      label: reviewStateLabel('ACCEPTED_UNVERIFIED'),
      color: 'bg-teal-100 text-teal-800',
      key: 'ACCEPTED_UNVERIFIED',
    };
  }
  if (review === 'VERIFIED') {
    return { label: reviewStateLabel('VERIFIED'), color: 'bg-green-100 text-green-800', key: 'VERIFIED' };
  }
  if (review === 'UNDER_REVIEW' || review === 'NEEDS_INFORMATION') {
    return {
      label: reviewStateLabel(review),
      color: 'bg-indigo-100 text-indigo-800',
      key: review,
    };
  }
  if (isExtractionConfirmationPending(doc)) {
    return { label: 'AI data needs review', color: 'bg-amber-100 text-amber-800', key: 'EXTRACTION_PENDING' };
  }
  const extractionStatus = String(doc.extraction_status || '').toUpperCase();
  if (extractionStatus === 'PENDING' || doc.ai_extraction?.status === 'pending') {
    return { label: 'Extraction in progress', color: 'bg-blue-100 text-blue-800', key: 'PROCESSING' };
  }
  return { label: reviewStateLabel(review), color: 'bg-gray-100 text-gray-700', key: review || 'UPLOADED' };
}

/**
 * Secondary extraction pipeline badge (subordinate to evidence decision).
 * @param {Record<string, unknown>} doc
 * @param {string|null} extractingDocumentId
 */
export function getClientExtractionPipelineBadge(doc = {}, extractingDocumentId = null) {
  if (extractingDocumentId && doc.document_id === extractingDocumentId) {
    return { label: 'Extracting…', color: 'bg-blue-100 text-blue-800' };
  }
  const op = String(doc.document_operational_state || '');
  if (op === 'EVIDENCE_ACCEPTED_ON_FILE' || op === 'EVIDENCE_VERIFIED' || op === 'EXTERNALLY_VERIFIED') {
    return { label: 'Confirmed by review', color: 'bg-green-100 text-green-800' };
  }
  if (op === 'EVIDENCE_REJECTED') {
    return { label: 'Not applied — rejected', color: 'bg-gray-100 text-gray-600' };
  }
  if (op === 'MATCH_RESOLVED_VERIFICATION_PENDING') {
    return { label: 'Verification still pending', color: 'bg-sky-100 text-sky-900' };
  }
  if (isAdminEvidenceDecisionAccepted(doc)) {
    return { label: 'Confirmed by review', color: 'bg-green-100 text-green-800' };
  }
  if (isAdminEvidenceDecisionRejected(doc)) {
    return { label: 'Not applied — rejected', color: 'bg-gray-100 text-gray-600' };
  }
  const extractionStatus = String(doc.extraction_status || '').toUpperCase();
  if (extractionStatus === 'FAILED' || doc.ai_extraction?.status === 'failed') {
    return { label: 'Extraction failed', color: 'bg-red-100 text-red-800' };
  }
  if (isExtractionConfirmationPending(doc)) {
    return { label: 'Awaiting your confirmation', color: 'bg-amber-100 text-amber-800' };
  }
  if (extractionStatus === 'PENDING') {
    return { label: 'Extraction in progress', color: 'bg-blue-100 text-blue-800' };
  }
  return null;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function shouldShowReviewAndApplyData(doc = {}) {
  if (!isExtractionConfirmationPending(doc)) {
    return false;
  }
  if (!doc.ai_extraction?.data && doc.extraction_status !== 'EXTRACTED' && doc.extraction_status !== 'NEEDS_REVIEW') {
    return false;
  }
  return true;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function shouldShowViewExtractedDataAction(doc = {}) {
  const hasData = Boolean(doc.ai_extraction?.data);
  if (!hasData) return false;
  return isAdminEvidenceDecisionAccepted(doc) || isAdminEvidenceDecisionRejected(doc) || hasAdminSupersededExtractionConfirmation(doc);
}

/**
 * @param {Record<string, unknown>} doc
 */
export function shouldShowAiExtractedDataPanel(doc = {}) {
  const extractionFailed = doc.extraction_status === 'FAILED' || doc.ai_extraction?.status === 'failed';
  if (extractionFailed) return false;
  const hasCompletedExtraction = doc.ai_extraction?.status === 'completed' && doc.ai_extraction?.data;
  return Boolean(hasCompletedExtraction);
}

/**
 * @param {Record<string, unknown>} doc
 */
export function getClientDocumentRowStatusLabel(doc = {}) {
  if (doc.document_operational_label) {
    return String(doc.document_operational_label);
  }
  const badge = getClientDocumentEvidenceBadge(doc);
  return badge.label;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isPendingConfirmationForRequirementAttention(doc = {}) {
  if (doc.document_operational_state === 'MATCH_RESOLVED_VERIFICATION_PENDING') {
    return false;
  }
  const hasExtraction = doc?.extraction_id || (doc?.ai_extraction?.status === 'completed' && doc?.ai_extraction?.data);
  return Boolean(hasExtraction) && isExtractionConfirmationPending(doc) && !isPositiveEvidenceState(doc);
}
