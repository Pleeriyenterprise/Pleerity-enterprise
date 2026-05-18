import {
  isSubmissionAwaitingReview,
  requirementHasPersistedClientSubmission,
  resolveClientRequirementLifecycleForPresentation,
  resolveSubmissionAwareEvidenceBadgeLabel,
} from './clientPersistedSubmissionPresentation';

describe('clientPersistedSubmissionPresentation', () => {
  const rowWithCer = {
    requirement_id: 'r1',
    client_lifecycle_state: 'ACTION_REQUIRED',
    client_lifecycle_reason_codes: ['EA:MISSING'],
    evidence_authority: {
      state: 'MISSING',
      primary_evidence_record_id: 'cer_abc',
    },
    evidence_badge_label: 'Not uploaded',
    workflow_class: 'GUIDED_DECLARATION',
    take_action: {
      primary: {
        label: 'Record Wales occupation contract',
        handler: 'guided_evidence',
      },
    },
  };

  it('detects persisted submission via primary_evidence_record_id', () => {
    expect(requirementHasPersistedClientSubmission(rowWithCer)).toBe(true);
    expect(isSubmissionAwaitingReview(rowWithCer)).toBe(true);
  });

  it('elevates presentation lifecycle to PENDING_REVIEW when submission on file', () => {
    const lc = resolveClientRequirementLifecycleForPresentation(rowWithCer);
    expect(lc.state).toBe('PENDING_REVIEW');
    expect(lc.label).toBe('Awaiting review');
  });

  it('replaces misleading not-uploaded badge', () => {
    expect(resolveSubmissionAwareEvidenceBadgeLabel('Not uploaded', rowWithCer)).toBe('Submission received');
  });

  it('leaves badge unchanged when no submission', () => {
    const row = { client_lifecycle_state: 'ACTION_REQUIRED', evidence_badge_label: 'Not uploaded' };
    expect(resolveSubmissionAwareEvidenceBadgeLabel('Not uploaded', row)).toBe('Not uploaded');
  });
});
