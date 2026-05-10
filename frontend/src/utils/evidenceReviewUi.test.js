import {
  assuranceTierLabel,
  clientFacingVerificationLabel,
  effectiveAssuranceTier,
  effectiveEvidenceReviewState,
  isPositiveEvidenceState,
  reviewStateLabel,
} from './evidenceReviewUi';

describe('evidenceReviewUi', () => {
  it('falls back legacy VERIFIED safely', () => {
    const doc = { status: 'VERIFIED' };
    expect(effectiveEvidenceReviewState(doc)).toBe('ACCEPTED_UNVERIFIED');
    expect(effectiveAssuranceTier(doc)).toBe('HUMAN_ACCEPTED');
  });

  it('maps assurance tier externally verified when evidence_review_state is absent', () => {
    expect(
      effectiveEvidenceReviewState({
        assurance_tier: 'EXTERNALLY_VERIFIED',
        status: 'UPLOADED',
      }),
    ).toBe('VERIFIED');
    expect(clientFacingVerificationLabel({ assurance_tier: 'EXTERNALLY_VERIFIED', status: 'UPLOADED' })).toBe(
      'Externally verified',
    );
  });

  it('shows externally verified only for EXTERNALLY_VERIFIED tier', () => {
    expect(clientFacingVerificationLabel({ assurance_tier: 'EXTERNALLY_VERIFIED' })).toBe('Externally verified');
    expect(clientFacingVerificationLabel({ status: 'VERIFIED' })).not.toBe('Externally verified');
  });

  it('keeps ACCEPTED_UNVERIFIED visually distinct from VERIFIED', () => {
    expect(reviewStateLabel('ACCEPTED_UNVERIFIED')).toBe('Accepted (unverified)');
    expect(reviewStateLabel('VERIFIED')).toBe('Verified');
    expect(assuranceTierLabel('HUMAN_ACCEPTED')).toBe('Human accepted');
    expect(assuranceTierLabel('EXTERNALLY_VERIFIED')).toBe('Externally verified');
  });

  it('treats rejected/expired/needs info as non-positive evidence', () => {
    expect(isPositiveEvidenceState({ evidence_review_state: 'REJECTED' })).toBe(false);
    expect(isPositiveEvidenceState({ evidence_review_state: 'EXPIRED' })).toBe(false);
    expect(isPositiveEvidenceState({ evidence_review_state: 'NEEDS_INFORMATION' })).toBe(false);
    expect(isPositiveEvidenceState({ evidence_review_state: 'ACCEPTED_UNVERIFIED' })).toBe(true);
  });
});

