import {
  isSubmissionAwaitingReview,
  resolveClientRequirementLifecycleForPresentation,
  submissionAwaitingReviewSubline,
} from './clientPersistedSubmissionPresentation';

describe('clientPersistedSubmissionPresentation phase1', () => {
  const smokeWithGovernance = {
    requirement_id: 'r1',
    governance_family: 'SELF_CERTIFIED',
    truth_presentation_stage: 'operational_incomplete',
    truth_presentation_label: 'Additional action still required',
    truth_presentation_subline: 'Some required evidence components are still missing.',
    client_lifecycle_state: 'ACTION_REQUIRED',
    evidence_authority: { state: 'MISSING', primary_evidence_record_id: 'cer_abc' },
    queue_backed_review: false,
  };

  it('does not elevate to generic Awaiting review when governance truth present', () => {
    const lc = resolveClientRequirementLifecycleForPresentation(smokeWithGovernance);
    expect(lc.label).toBe('Additional action still required');
    expect(lc.label).not.toMatch(/awaiting review/i);
    expect(lc.state).toBe('ACTION_REQUIRED');
  });

  it('does not treat non-queue submission as awaiting review', () => {
    expect(isSubmissionAwaitingReview(smokeWithGovernance)).toBe(false);
  });

  it('uses governance subline instead of generic awaiting review copy', () => {
    expect(submissionAwaitingReviewSubline(smokeWithGovernance)).toBe(
      'Some required evidence components are still missing.',
    );
  });

  it('queue-backed platform review still awaits review', () => {
    const gas = {
      governance_family: 'PLATFORM_VERIFIED',
      truth_presentation_stage: 'platform_verification_pending',
      truth_presentation_label: 'Platform verification pending',
      queue_backed_review: true,
      review_owner: 'platform_admin',
      client_lifecycle_state: 'PENDING_REVIEW',
      evidence_authority: { state: 'PENDING_ADMIN_REVIEW', primary_evidence_record_id: 'd1' },
    };
    expect(isSubmissionAwaitingReview(gas)).toBe(true);
    const lc = resolveClientRequirementLifecycleForPresentation(gas);
    expect(lc.label).toBe('Platform verification pending');
  });
});
