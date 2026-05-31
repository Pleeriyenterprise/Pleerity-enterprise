import { composeRequirementStatusBadgeVisibility } from './documentEvidenceAuthority';

describe('composeRequirementStatusBadgeVisibility phase1', () => {
  it('hides duplicate tier when status and tier share semantics', () => {
    const req = {
      truth_presentation_label: 'Additional action still required',
      truth_presentation_stage: 'operational_incomplete',
      client_lifecycle_state: 'ACTION_REQUIRED',
      queue_backed_review: false,
    };
    const vis = composeRequirementStatusBadgeVisibility(
      req,
      { text: 'Additional action still required' },
      { text: 'Additional action still required' },
      null,
    );
    expect(vis.showTier).toBe(false);
  });

  it('hides generic awaiting review tier without queue owner', () => {
    const req = { queue_backed_review: false };
    const vis = composeRequirementStatusBadgeVisibility(
      req,
      { text: 'Declaration recorded' },
      { text: 'Awaiting review' },
      null,
    );
    expect(vis.showTier).toBe(false);
  });
});
