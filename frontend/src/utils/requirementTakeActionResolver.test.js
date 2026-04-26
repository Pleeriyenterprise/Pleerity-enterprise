import {
  mergeRequirementSupportingLinks,
  requirementUsesServerTakeActionPrimary,
  resolveRequirementAction,
} from './requirementTakeActionResolver';

describe('requirementTakeActionResolver', () => {
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
});
