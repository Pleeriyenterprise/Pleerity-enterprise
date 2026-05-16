import {
  getClientDocumentEvidenceBadge,
  getClientExtractionPipelineBadge,
  hasCanonicalOperationalState,
  isExtractionConfirmationPending,
  isPendingConfirmationForRequirementAttention,
  shouldShowReviewAndApplyData,
  shouldShowViewExtractedDataAction,
} from './documentClientPresentation';

const adminAcceptedDoc = {
  document_id: 'd1',
  status: 'VERIFIED',
  evidence_review_state: 'ACCEPTED_UNVERIFIED',
  assurance_tier: 'HUMAN_ACCEPTED',
  extraction_status: 'NEEDS_REVIEW',
  ai_extraction: {
    status: 'completed',
    review_status: 'PENDING',
    data: { certificate_number: 'ABC' },
  },
};

const adminAcceptedSupersededDoc = {
  ...adminAcceptedDoc,
  extraction_confirmation_superseded: true,
  extraction_status: 'CONFIRMED',
  ai_extraction: {
    ...adminAcceptedDoc.ai_extraction,
    review_status: 'approved',
    superseded_by_admin_decision: 'accepted',
  },
};

const pendingExtractionDoc = {
  document_id: 'd2',
  status: 'UPLOADED',
  evidence_review_state: 'UPLOADED',
  extraction_status: 'NEEDS_REVIEW',
  ai_extraction: {
    status: 'completed',
    review_status: 'PENDING',
    data: { certificate_number: 'XYZ' },
  },
};

const rejectedDoc = {
  document_id: 'd3',
  status: 'REJECTED',
  evidence_review_state: 'REJECTED',
  assurance_tier: 'REJECTED',
  extraction_status: 'NEEDS_REVIEW',
  ai_extraction: {
    status: 'completed',
    review_status: 'PENDING',
    data: { certificate_number: 'BAD' },
  },
};

describe('documentClientPresentation precedence', () => {
  it('admin accepted evidence does not show extraction confirmation pending', () => {
    expect(isExtractionConfirmationPending(adminAcceptedDoc)).toBe(false);
    expect(shouldShowReviewAndApplyData(adminAcceptedDoc)).toBe(false);
  });

  it('admin accepted with supersession flags hides Review & Apply', () => {
    expect(shouldShowReviewAndApplyData(adminAcceptedSupersededDoc)).toBe(false);
    expect(shouldShowViewExtractedDataAction(adminAcceptedSupersededDoc)).toBe(true);
  });

  it('primary badge shows accepted on file after admin verify, not awaiting confirmation', () => {
    const badge = getClientDocumentEvidenceBadge(adminAcceptedDoc);
    expect(badge.key).toBe('ACCEPTED_UNVERIFIED');
    expect(badge.label).toContain('Accepted on file');
    expect(badge.label).not.toMatch(/awaiting confirmation/i);
  });

  it('secondary pipeline badge shows confirmed by review after admin accept', () => {
    const pipeline = getClientExtractionPipelineBadge(adminAcceptedDoc);
    expect(pipeline.label).toBe('Confirmed by review');
  });

  it('pending extraction without admin decision shows Review & Apply', () => {
    expect(isExtractionConfirmationPending(pendingExtractionDoc)).toBe(true);
    expect(shouldShowReviewAndApplyData(pendingExtractionDoc)).toBe(true);
    const badge = getClientDocumentEvidenceBadge(pendingExtractionDoc);
    expect(badge.key).toBe('EXTRACTION_PENDING');
    expect(badge.label).toBe('AI data needs review');
  });

  it('rejected admin decision shows rejected badge and hides Review & Apply', () => {
    expect(shouldShowReviewAndApplyData(rejectedDoc)).toBe(false);
    const badge = getClientDocumentEvidenceBadge(rejectedDoc);
    expect(badge.key).toBe('REJECTED');
    const pipeline = getClientExtractionPipelineBadge(rejectedDoc);
    expect(pipeline.label).toContain('rejected');
  });

  it('requirement attention pending only when extraction still needs confirm and not accepted', () => {
    expect(isPendingConfirmationForRequirementAttention(pendingExtractionDoc)).toBe(true);
    expect(isPendingConfirmationForRequirementAttention(adminAcceptedDoc)).toBe(false);
  });

  it('uses canonical operational state when provided by API', () => {
    const canonical = {
      ...adminAcceptedDoc,
      document_operational_state: 'EVIDENCE_ACCEPTED_ON_FILE',
      document_operational_label: 'Accepted on file (not externally verified)',
      document_operational_reason_codes: ['EVIDENCE_ACCEPTED_ON_FILE', 'EXTRACTION_CONFIRMATION_SUPERSEDED'],
    };
    expect(hasCanonicalOperationalState(canonical)).toBe(true);
    expect(isExtractionConfirmationPending(canonical)).toBe(false);
    expect(shouldShowReviewAndApplyData(canonical)).toBe(false);
    const badge = getClientDocumentEvidenceBadge(canonical);
    expect(badge.key).toBe('ACCEPTED_UNVERIFIED');
    expect(badge.label).toContain('Accepted on file');
  });

  it('match resolved pending verification does not show Review and Apply', () => {
    const matchPending = {
      document_id: 'd-match',
      status: 'UPLOADED',
      document_operational_state: 'MATCH_RESOLVED_VERIFICATION_PENDING',
      document_operational_label: 'Requirement linked — verification still pending',
      ai_extraction: { status: 'completed', review_status: 'PENDING', data: { x: 1 } },
      extraction_status: 'NEEDS_REVIEW',
    };
    expect(isExtractionConfirmationPending(matchPending)).toBe(false);
    expect(shouldShowReviewAndApplyData(matchPending)).toBe(false);
    const pipeline = getClientExtractionPipelineBadge(matchPending);
    expect(pipeline.label).toContain('Verification still pending');
  });
});
