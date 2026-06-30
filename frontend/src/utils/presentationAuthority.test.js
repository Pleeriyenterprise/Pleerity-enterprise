import {
  parsePortalRequirementCounts,
  requirementCountHeadlineLines,
  shouldShowDocumentsSetupStep,
} from './presentationAuthority';

describe('parsePortalRequirementCounts', () => {
  it('reads semantic setup-status fields when present', () => {
    const c = parsePortalRequirementCounts({
      requirements_count: 18,
      requirements_runtime_visible_count: 14,
      requirements_tracked_attention_count: 12,
      requirements_count_semantics: 'tracked_attention_document_job_excludes_obligation',
    });
    expect(c.rawApplicable).toBe(18);
    expect(c.trackedAttention).toBe(12);
    expect(c.hasSemanticFields).toBe(true);
  });

  it('falls back when semantic fields absent', () => {
    const c = parsePortalRequirementCounts({ requirements_count: 5 });
    expect(c.hasSemanticFields).toBe(false);
    expect(c.rawApplicable).toBe(5);
  });
});

describe('requirementCountHeadlineLines', () => {
  it('explains when identified count exceeds tracked', () => {
    const lines = requirementCountHeadlineLines(
      parsePortalRequirementCounts({
        requirements_count: 18,
        requirements_runtime_visible_count: 14,
        requirements_tracked_attention_count: 12,
      }),
    );
    expect(lines.primary).toBe(12);
    expect(lines.secondary).toBe(18);
    expect(lines.footnote).toMatch(/Nothing has been removed/);
  });
});

describe('shouldShowDocumentsSetupStep', () => {
  it('uses backend setup_presentation authority', () => {
    expect(
      shouldShowDocumentsSetupStep({
        setup_presentation: { documents_step_recommended: true, authority: 'onboarding_checklist' },
      }),
    ).toBe(true);
    expect(
      shouldShowDocumentsSetupStep({
        setup_presentation: { documents_step_recommended: false },
      }),
    ).toBe(false);
    expect(shouldShowDocumentsSetupStep({})).toBe(false);
  });
});
