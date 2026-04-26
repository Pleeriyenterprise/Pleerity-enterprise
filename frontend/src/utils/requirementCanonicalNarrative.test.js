import { pickWhyItMattersForDisplay, pickCanonicalWhyItMattersShort } from './requirementCanonicalNarrative';

describe('requirementCanonicalNarrative', () => {
  it('resolves jurisdiction-specific published copy only (not other regions)', () => {
    const merged = {
      property_jurisdiction: 'England',
      registry_metadata: {
        why_it_matters_by_jurisdiction_published: {
          England: { why_it_matters_short: 'England-specific short', why_it_matters_long: 'England long body' },
          Wales: { why_it_matters_short: 'Wales should not appear' },
        },
        why_it_matters_short_published: 'Fallback flat published',
      },
    };
    const w = pickWhyItMattersForDisplay(merged);
    expect(w.source).toBe('published_jurisdiction');
    expect(w.short).toBe('England-specific short');
    expect(w.long).toBe('England long body');
    expect(w.jurisdictionRulesLabel).toBe('England');
    expect(pickCanonicalWhyItMattersShort(merged)).toBe('England-specific short');
  });

  it('falls back to flat published when no jurisdiction map match', () => {
    const merged = {
      property_jurisdiction: 'Scotland',
      registry_metadata: {
        why_it_matters_by_jurisdiction_published: {
          England: { why_it_matters_short: 'Only England' },
        },
        why_it_matters_short_published: 'Flat published',
      },
    };
    const w = pickWhyItMattersForDisplay(merged);
    expect(w.source).toBe('published');
    expect(w.short).toBe('Flat published');
  });
});
