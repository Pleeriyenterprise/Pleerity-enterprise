import {
  SCORE_AREA_LABELS,
  SCORING_EXPLANATION_FORBIDDEN_TERMS,
  SCORE_FRAMEWORK_INTRO,
  SCORE_METHODOLOGY_INTRO,
  SCORE_ADVANCED_DETAILS_BODY,
  SCORE_DEFINITIONS,
} from './scoringExplanationCopy';

describe('scoringExplanationCopy trust hardening', () => {
  const allCopy = [
    ...Object.values(SCORE_AREA_LABELS),
    SCORE_FRAMEWORK_INTRO,
    SCORE_METHODOLOGY_INTRO,
    ...SCORE_ADVANCED_DETAILS_BODY,
    ...SCORE_DEFINITIONS.map((d) => `${d.term} ${d.definition}`),
  ].join(' ');

  it('avoids engineering leakage terms in shared copy', () => {
    const lower = allCopy.toLowerCase();
    for (const term of SCORING_EXPLANATION_FORBIDDEN_TERMS) {
      expect(lower).not.toContain(term.toLowerCase());
    }
  });

  it('uses human-friendly area labels', () => {
    expect(SCORE_AREA_LABELS.legal_core).toBe('Core legal requirements');
    expect(SCORE_AREA_LABELS.documentation_completeness).toBe('Accepted evidence');
  });
});
