import { canonicalComplianceInlineNarrative } from './complianceObligationPresent';

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
});
