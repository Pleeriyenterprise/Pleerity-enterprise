import { mergeRequirementIntelPayload, pickWhyItMattersForDisplay } from './requirementIntelligenceMerge';

describe('requirementIntelligenceMerge', () => {
  it('merges registry_metadata without dropping published keys from the seed row', () => {
    const seed = {
      requirement_id: 'r1',
      registry_metadata: {
        why_it_matters_short_published: 'Published short',
        action_links_published: [{ label: 'Gov', url: 'https://gov.example/x' }],
      },
    };
    const api = {
      requirement_id: 'r1',
      workflow_status: 'ACTION_REQUIRED',
      compliance_state: 'MISSING',
      registry_metadata: {
        why_it_matters_long_published: 'Published long',
      },
    };
    const m = mergeRequirementIntelPayload(seed, api);
    expect(m.workflow_status).toBe('ACTION_REQUIRED');
    expect(m.registry_metadata.why_it_matters_short_published).toBe('Published short');
    expect(m.registry_metadata.why_it_matters_long_published).toBe('Published long');
    expect(m.registry_metadata.action_links_published).toHaveLength(1);
  });

  it('pickWhyItMattersForDisplay prefers published copy when present', () => {
    const merged = {
      registry_metadata: {
        why_it_matters_short_published: 'Reg short',
        why_it_matters_long_published: 'Reg long',
      },
      why_it_matters_short: 'Generic short',
      why_it_matters_long: 'Generic long',
    };
    const w = pickWhyItMattersForDisplay(merged);
    expect(w.source).toBe('published');
    expect(w.short).toBe('Reg short');
    expect(w.long).toBe('Reg long');
  });

  it('pickWhyItMattersForDisplay falls back to generic when published absent', () => {
    const merged = {
      registry_metadata: {},
      why_it_matters_short: 'G short',
      why_it_matters_long: 'G long',
    };
    const w = pickWhyItMattersForDisplay(merged);
    expect(w.source).toBe('generic');
    expect(w.short).toBe('G short');
  });
});
