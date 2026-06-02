import { resolveAssuranceTier, assuranceTierSummary, ASSURANCE_SELF_RECORDED } from './assurancePresentation';

describe('assurancePresentation', () => {
  it('resolves self-recorded from API tier', () => {
    expect(resolveAssuranceTier({ assurance_tier: 'SELF_RECORDED' })).toBe(ASSURANCE_SELF_RECORDED);
  });

  it('does not treat org verification as platform', () => {
    expect(
      resolveAssuranceTier({
        truth_presentation_stage: 'declaration_recorded',
        governance_family: 'SELF_CERTIFIED',
      }),
    ).toBe(ASSURANCE_SELF_RECORDED);
  });

  it('summarises self-recorded without org reviewer wording', () => {
    const s = assuranceTierSummary(ASSURANCE_SELF_RECORDED);
    expect(s.title).toMatch(/Recorded on file/i);
    expect(s.guidance).not.toMatch(/organisation admin/i);
  });
});
