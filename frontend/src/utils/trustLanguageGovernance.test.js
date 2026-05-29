import {
  FORBIDDEN_ENGINEERING_TERMS,
  validateCustomerCopy,
  COPY_AUTHORITY_REGISTRY,
} from './trustLanguageGovernance';
import {
  SCORE_AREA_LABELS,
  SCORE_FRAMEWORK_DISCLAIMER,
  SCORING_EXPLANATION_FORBIDDEN_TERMS,
} from './scoringExplanationCopy';

describe('trustLanguageGovernance', () => {
  it('detects engineering language', () => {
    expect(validateCustomerCopy('The scoring engine recalculated')).not.toHaveLength(0);
  });

  it('detects false precision', () => {
    expect(validateCustomerCopy('Score +12 after upload')).not.toHaveLength(0);
  });

  it('registry includes scoring authorities', () => {
    expect(COPY_AUTHORITY_REGISTRY.portal_scoring_ui).toContain('scoringExplanationCopy');
    expect(COPY_AUTHORITY_REGISTRY.backend_governance).toContain('trust_language_governance');
  });

  it('scoring copy re-exports forbidden terms from governance', () => {
    expect(SCORING_EXPLANATION_FORBIDDEN_TERMS.length).toBeGreaterThan(0);
    expect(FORBIDDEN_ENGINEERING_TERMS).toEqual(
      expect.arrayContaining(SCORING_EXPLANATION_FORBIDDEN_TERMS)
    );
  });

  it('portal scoring constants pass governance scan', () => {
    const blob = [
      ...Object.values(SCORE_AREA_LABELS),
      SCORE_FRAMEWORK_DISCLAIMER,
    ].join('\n');
    for (const term of SCORING_EXPLANATION_FORBIDDEN_TERMS) {
      expect(blob.toLowerCase()).not.toContain(term.toLowerCase());
    }
  });
});
