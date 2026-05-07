import {
  mergeRequirementSupportingLinks,
  requirementUsesServerTakeActionPrimary,
  resolveRequirementAction,
} from './requirementTakeActionResolver';

describe('requirementTakeActionResolver', () => {
  const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

  beforeEach(() => {
    warnSpy.mockClear();
  });

  afterAll(() => {
    warnSpy.mockRestore();
  });

  it('warns when take_action envelope is missing (drift guard)', () => {
    const req = {
      requirement_id: 'r1',
      property_id: 'p1',
      requirement_code: 'gas_safety',
      requirement_type: 'gas_safety',
      compliance_requirement_class: 'DOCUMENT',
    };
    resolveRequirementAction(req, {});
    expect(warnSpy).toHaveBeenCalled();
  });

  it('job fallback uses evidence-first legionella label without Book', () => {
    const req = {
      requirement_id: 'r1',
      property_id: 'p1',
      requirement_code: 'legionella',
      requirement_type: 'legionella',
      compliance_requirement_class: 'JOB',
    };
    const out = resolveRequirementAction(req, {});
    expect(out.primary_action_label).toContain('Upload completed legionella');
    expect(out.primary_action_label).not.toMatch(/Book/i);
  });

  it('uses API take_action primary when present', () => {
    const req = {
      take_action: {
        primary: { label: 'Custom upload label', route: '/documents?property_id=p1&requirement_id=r1', handler: 'navigate' },
        secondary: null,
        supporting_external_links: [],
      },
      compliance_requirement_class: 'DOCUMENT',
    };
    expect(requirementUsesServerTakeActionPrimary(req)).toBe(true);
    const out = resolveRequirementAction(req, {});
    expect(out.primary_action_label).toBe('Custom upload label');
    expect(out.primary_route).toContain('/documents');
  });

  it('detects missing server primary for drift guard', () => {
    const req = { take_action: { primary: null, supporting_external_links: [] } };
    expect(requirementUsesServerTakeActionPrimary(req)).toBe(false);
  });

  it('does not fall back to Upload document when take_action is suppressed', () => {
    const req = {
      take_action: { suppressed: true, primary: null, secondary: null, supporting_external_links: [] },
      compliance_requirement_class: 'DOCUMENT',
    };
    const out = resolveRequirementAction(req, {});
    expect(out.primary_action_label).not.toBe('Upload document');
    expect(out.primary_action_handler).toBe('none');
  });

  it('merges action_links_published with take_action supporting links without duplicate URLs', () => {
    const req = {
      take_action: {
        primary: { label: 'Go', route: '/documents?property_id=p1&requirement_id=r1', handler: 'navigate' },
        supporting_external_links: [{ label: 'Gov', url: 'https://example.com/a', key: 'a' }],
      },
      action_links: [],
      registry_metadata: {
        action_links_published: [{ label: 'Gov', url: 'https://example.com/a', key: 'a_dup' }, { label: 'Other', url: 'https://example.com/b', key: 'b' }],
      },
    };
    const links = mergeRequirementSupportingLinks(req);
    expect(links).toHaveLength(2);
    expect(links.map((x) => x.url)).toEqual(['https://example.com/a', 'https://example.com/b']);
  });

  it('treats guided_evidence_resolution primary as server-authoritative without route', () => {
    const req = {
      take_action: {
        primary: {
          label: 'Resolve requirement',
          route: null,
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence',
          intent: 'guided_evidence_resolution',
          property_id: 'p1',
          requirement_id: 'r1',
        },
        secondary: {
          label: 'Upload CP12',
          route: '/documents?property_id=p1&requirement_id=r1',
          handler: 'navigate',
          external: false,
        },
        supporting_external_links: [],
      },
      compliance_requirement_class: 'DOCUMENT',
    };
    expect(requirementUsesServerTakeActionPrimary(req)).toBe(true);
    const out = resolveRequirementAction(req, {});
    expect(out.primary_action_handler).toBe('guided_evidence');
    expect(out.primary_route).toBeNull();
    expect(out.secondary_action?.route).toContain('/documents');
  });

  it('maps guided_evidence_unavailable to guided_evidence_error handler', () => {
    const req = {
      take_action: {
        primary: {
          label: 'Guided resolution unavailable',
          route: null,
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence_unavailable',
          intent: 'guided_evidence_unavailable',
          metadata_incomplete: true,
        },
        secondary: {
          label: 'Upload document',
          route: '/documents',
          handler: 'navigate',
          external: false,
        },
        supporting_external_links: [],
      },
      compliance_requirement_class: 'DOCUMENT',
    };
    const out = resolveRequirementAction(req, {});
    expect(out.primary_action_handler).toBe('guided_evidence_error');
    expect(out.secondary_action?.route).toContain('/documents');
  });

  it('fallback does not treat engine obligation posture as guidance when class is DOCUMENT (external assessment parity)', () => {
    const req = {
      requirement_id: 'r1',
      property_id: 'p1',
      requirement_code: 'lead_testing',
      requirement_type: 'lead_testing',
      compliance_requirement_class: 'DOCUMENT',
      engine_fulfillment_mode: 'obligation',
      engine_informational: true,
    };
    const out = resolveRequirementAction(req, {});
    expect(out.primary_intent).toBe('upload_evidence');
    expect(out.primary_action_label).not.toMatch(/view guidance/i);
  });

  it('registry primary_action_mode hidden infers obligation and shows no upload primary in fallback', () => {
    const req = {
      requirement_id: 'r1',
      property_id: 'p1',
      requirement_code: 'x',
      compliance_requirement_class: 'DOCUMENT',
      registry_metadata: { primary_action_mode: 'hidden' },
    };
    const out = resolveRequirementAction(req, {});
    expect(out.actionType).toBe('OBLIGATION');
    expect(out.primary_intent).toBe('view_guidance');
  });

  it('document-only take_action keeps direct upload handler', () => {
    const req = {
      take_action: {
        primary: {
          label: 'Upload Gas Safety record',
          route: '/documents?property_id=p1&requirement_id=r1',
          kind: 'navigate',
          handler: 'navigate',
          intent: 'upload_evidence',
        },
        secondary: null,
        supporting_external_links: [],
      },
      compliance_requirement_class: 'DOCUMENT',
    };
    const out = resolveRequirementAction(req, {});
    expect(out.primary_action_handler).toBe('navigate');
    expect(out.secondary_action).toBeNull();
  });
});
