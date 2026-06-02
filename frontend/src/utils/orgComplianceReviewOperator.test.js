import {
  humanizeEvidenceConfidence,
  requirementEligibleForOrgOperatorReview,
  resolveOrgReviewEvidenceRecordId,
  cerAwaitingOrgVerification,
} from './orgComplianceReviewOperator';

describe('orgComplianceReviewOperator', () => {
  it('eligible only for org queue governance invariant', () => {
    expect(
      requirementEligibleForOrgOperatorReview({
        governance_family: 'ORG_ADMIN_REVIEWED',
        queue_backed_review: true,
        review_owner: 'org_admin',
      }),
    ).toBe(true);
    expect(
      requirementEligibleForOrgOperatorReview({
        governance_family: 'ORG_ADMIN_REVIEWED',
        queue_backed_review: true,
        review_owner: 'platform_admin_escalation',
      }),
    ).toBe(false);
  });

  it('humanizes medium confidence for reviewers', () => {
    expect(humanizeEvidenceConfidence('MEDIUM')).toMatch(/still requires your review/i);
    expect(humanizeEvidenceConfidence('MEDIUM')).not.toMatch(/^Confidence: MEDIUM$/i);
  });

  it('resolves evidence record id from CER then authority', () => {
    expect(
      resolveOrgReviewEvidenceRecordId(
        { evidence_authority: { primary_evidence_record_id: 'ea-1' } },
        { evidence_record_id: 'cer-9' },
      ),
    ).toBe('cer-9');
    expect(resolveOrgReviewEvidenceRecordId({ primary_evidence_record_id: 'p-1' }, null)).toBe('p-1');
  });

  it('detects pending verification on CER', () => {
    expect(cerAwaitingOrgVerification({ verification_status: 'PENDING_REVIEW' })).toBe(true);
    expect(cerAwaitingOrgVerification({ verification_status: 'VERIFIED' })).toBe(false);
  });
});
