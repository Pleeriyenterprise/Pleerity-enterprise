import {
  backfillGovernanceTruthSurface,
  mapTruthStageToLifecycleState,
} from './cerGovernancePresentation';
import { resolveExistingSubmissionBannerCopy } from './clientPersistedSubmissionPresentation';

describe('backfillGovernanceTruthSurface', () => {
  it('maps component incomplete legacy row to operational_incomplete', () => {
    const out = backfillGovernanceTruthSurface({
      evidence_authority: { state_reason: 'multi_evidence_components_incomplete', primary_evidence_record_id: 'x' },
      evidence_completeness: { is_complete: false, required_missing_count: 1 },
    });
    expect(out.truth_presentation_stage).toBe('operational_incomplete');
    expect(mapTruthStageToLifecycleState(out.truth_presentation_stage, false)).toBe('ACTION_REQUIRED');
  });
});

describe('resolveExistingSubmissionBannerCopy', () => {
  it('avoids awaiting review when queue_backed_review is false', () => {
    const copy = resolveExistingSubmissionBannerCopy({
      evidence_authority: { primary_evidence_record_id: 'cer_1' },
      truth_presentation_stage: 'followup_required',
      queue_backed_review: false,
    });
    expect(copy.toLowerCase()).not.toContain('awaiting review');
    expect(copy.toLowerCase()).toMatch(/follow-up|update/);
  });
});
