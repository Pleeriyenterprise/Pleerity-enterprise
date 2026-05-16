/**
 * Client-facing document row presentation with admin evidence decision precedence.
 *
 * Precedence (highest first):
 * A. Rejected / invalid evidence
 * B. Admin accepted or externally verified evidence
 * C. Pending admin review
 * D. AI extraction awaiting user confirmation
 * E. Extraction in progress
 * F. Uploaded / unreviewed
 */

import {
  effectiveAssuranceTier,
  effectiveEvidenceReviewState,
  isPositiveEvidenceState,
  reviewStateLabel,
} from './evidenceReviewUi';

/**
 * @param {Record<string, unknown>} doc
 */
export function hasAdminSupersededExtractionConfirmation(doc = {}) {
  if (doc.extraction_confirmation_superseded === true) return true;
  const ai = doc.ai_extraction;
  if (ai && typeof ai === 'object' && ai.superseded_by_admin_decision) return true;
  return false;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isAdminEvidenceDecisionAccepted(doc = {}) {
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
  const review = effectiveEvidenceReviewState(doc);
  if (review === 'REJECTED') return true;
  return String(doc.status || '').toUpperCase() === 'REJECTED';
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isExtractionConfirmationPending(doc = {}) {
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
  if (!doc.ai_extraction?.data && doc.extraction_status !== 'EXTRACTED' && doc.extraction_status !== 'NEEDS_REVIEW') {
    return false;
  }
  return isExtractionConfirmationPending(doc);
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
  const badge = getClientDocumentEvidenceBadge(doc);
  return badge.label;
}

/**
 * @param {Record<string, unknown>} doc
 */
export function isPendingConfirmationForRequirementAttention(doc = {}) {
  const hasExtraction = doc?.extraction_id || (doc?.ai_extraction?.status === 'completed' && doc?.ai_extraction?.data);
  return Boolean(hasExtraction) && isExtractionConfirmationPending(doc) && !isPositiveEvidenceState(doc);
}
