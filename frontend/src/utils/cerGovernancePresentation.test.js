import {
  labelsDuplicateSemantics,
  mapTruthStageToLifecycleState,
  resolveGovernanceAwareLifecycle,
} from './cerGovernancePresentation';

describe('cerGovernancePresentation', () => {
  const smokeIncomplete = {
    governance_family: 'SELF_CERTIFIED',
    truth_presentation_stage: 'operational_incomplete',
    truth_presentation_label: 'Additional action still required',
    truth_presentation_subline: 'Some required evidence components are still missing.',
    client_lifecycle_state: 'ACTION_REQUIRED',
    evidence_authority: { state: 'MISSING', primary_evidence_record_id: 'cer_1' },
    queue_backed_review: false,
  };

  it('maps operational incomplete to ACTION_REQUIRED without generic review label', () => {
    const lc = resolveGovernanceAwareLifecycle(smokeIncomplete);
    expect(lc.state).toBe('ACTION_REQUIRED');
    expect(lc.label).toBe('Additional action still required');
    expect(lc.label).not.toMatch(/awaiting review/i);
  });

  it('maps platform verification pending to PENDING_REVIEW with owner-qualified label', () => {
    const row = {
      truth_presentation_stage: 'platform_verification_pending',
      truth_presentation_label: 'Platform verification pending',
      queue_backed_review: true,
      review_owner: 'platform_admin',
      client_lifecycle_state: 'PENDING_REVIEW',
    };
    expect(mapTruthStageToLifecycleState('platform_verification_pending', true)).toBe('PENDING_REVIEW');
    const lc = resolveGovernanceAwareLifecycle(row);
    expect(lc.label).toBe('Platform verification pending');
  });

  it('dedupes duplicate semantic labels', () => {
    expect(labelsDuplicateSemantics('Awaiting review', 'Awaiting review')).toBe(true);
    expect(labelsDuplicateSemantics('Declaration recorded', 'Evidence on file')).toBe(false);
  });
});
