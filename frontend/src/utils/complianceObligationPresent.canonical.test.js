import {
  canonicalComplianceInlineNarrative,
  complianceObligationPrimaryAction,
  complianceObligationStatusLabel,
  isRedundantUploadStyleSecondaryAction,
} from './complianceObligationPresent';

describe('canonicalComplianceInlineNarrative', () => {
  it('uses the same short why source as the intelligence modal (published short)', () => {
    const row = {
      requirement_id: 'r1',
      property_id: 'p1',
      property_jurisdiction: 'England',
      registry_metadata: {
        why_it_matters_short_published: 'Registry short line',
      },
      take_action: {
        primary: { label: 'Upload', route: '/documents?property_id=p1&requirement_id=r1', handler: 'navigate' },
        supporting_external_links: [],
      },
      compliance_requirement_class: 'DOCUMENT',
    };
    const out = canonicalComplianceInlineNarrative(row);
    expect(out.why_it_matters).toBe('Registry short line');
    expect(out.recommended_action_text).toContain('Upload');
  });

  it('keeps guided declaration semantics non-verified and action-oriented', () => {
    const row = {
      requirement_id: 'r-guided',
      property_id: 'p1',
      requirement_code: 'right_to_rent',
      workflow_class: 'GUIDED_DECLARATION',
      status: 'MISSING',
      take_action: {
        primary: {
          label: 'Record declaration',
          route: '/properties/p1?open=resolve&requirement_id=r-guided',
          handler: 'guided_evidence',
        },
      },
    };
    expect(complianceObligationStatusLabel(row)).toBe('Declaration not recorded — action required');
    const action = complianceObligationPrimaryAction(row);
    expect(action.verb).toBe('resolve');
    expect(action.label).toBe('Record declaration');
  });

  it('keeps external assessment semantics as incomplete, not remediated', () => {
    const row = {
      requirement_id: 'r-assess',
      property_id: 'p1',
      requirement_code: 'legionella',
      workflow_class: 'EXTERNAL_ASSESSMENT_EVIDENCE',
      status: 'MISSING',
      take_action: {
        primary: {
          label: 'Upload assessment',
          route: '/documents?property_id=p1&requirement_id=r-assess',
          handler: 'navigate',
        },
      },
    };
    expect(complianceObligationStatusLabel(row)).toBe('Assessment not recorded — action required');
    expect(canonicalComplianceInlineNarrative(row).recommended_action_text).toContain('Upload assessment');
  });

  it('keeps condition-standard rows operational-safe', () => {
    const row = {
      requirement_id: 'r-cond',
      property_id: 'p1',
      requirement_code: 'fitness_for_human_habitation',
      workflow_class: 'GUIDANCE_ONLY',
      status: 'MISSING',
      take_action: {
        primary: {
          label: 'Review condition status',
          route: '/properties/p1?open=resolve&requirement_id=r-cond',
          handler: 'guided_evidence',
        },
      },
    };
    expect(complianceObligationStatusLabel(row)).toBe('Condition status needs review');
  });
});

describe('isRedundantUploadStyleSecondaryAction', () => {
  it('treats Documents routes and upload labels as redundant next to a guided primary', () => {
    expect(
      isRedundantUploadStyleSecondaryAction({
        secondary_action: { label: 'Upload document', route: '/documents?property_id=p1' },
      }),
    ).toBe(true);
    expect(
      isRedundantUploadStyleSecondaryAction({
        secondary_action: { label: 'Upload supporting evidence', route: '/foo' },
      }),
    ).toBe(true);
  });

  it('keeps non-upload secondaries available for compliance action strips', () => {
    expect(
      isRedundantUploadStyleSecondaryAction({
        secondary_action: { label: 'Book inspection', route: '/maintenance?property_id=p1' },
      }),
    ).toBe(false);
  });
});
