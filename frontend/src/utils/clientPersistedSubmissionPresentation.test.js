import {
  dispatchSupportingUploadAttribution,
  isSubmissionAwaitingReview,
  requirementHasPersistedClientSubmission,
  resolveClientRequirementLifecycleForPresentation,
  resolveSubmissionAwareEvidenceBadgeLabel,
  resolveStaticSupportingUploadDisclaimer,
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

  it('replaces misleading not-uploaded badge with on-file semantics', () => {
    expect(resolveSubmissionAwareEvidenceBadgeLabel('Not uploaded', rowWithCer)).toBe('Submission on file');
  });

  it('dispatches supporting upload attribution event', () => {
    const handler = jest.fn();
    window.addEventListener('compliance-supporting-upload', handler);
    dispatchSupportingUploadAttribution({ requirement_id: 'r1', property_id: 'p1' });
    window.removeEventListener('compliance-supporting-upload', handler);
    expect(handler).toHaveBeenCalled();
    expect(handler.mock.calls[0][0].detail.requirement_id).toBe('r1');
  });

  it('leaves badge unchanged when no submission', () => {
    const row = { client_lifecycle_state: 'ACTION_REQUIRED', evidence_badge_label: 'Not uploaded' };
    expect(resolveSubmissionAwareEvidenceBadgeLabel('Not uploaded', row)).toBe('Not uploaded');
  });
});
