import { resolveTaskCta } from './ctaRegistry';

describe('resolveTaskCta guided evidence', () => {
  it('returns guidedEvidence for requirement tasks with guided take_action primary', () => {
    const task = {
      source_type: 'requirement',
      primary_action_type: 'guided_evidence_resolution',
      property_id: 'p1',
      metadata: {
        take_action: {
          primary: {
            kind: 'guided_evidence_resolution',
            property_id: 'p1',
            requirement_id: 'r1',
            label: 'Resolve requirement',
          },
        },
      },
    };
    const cta = resolveTaskCta(task, 'primary');
    expect(cta.guidedEvidence).toEqual({ propertyId: 'p1', requirementId: 'r1', initialEvidenceMode: null });
    expect(cta.route).toBe('');
    expect(cta.action_type).toBe('guided_evidence_resolution');
  });

  it('returns initialEvidenceMode for direct_evidence_action primary', () => {
    const task = {
      source_type: 'requirement',
      primary_action_type: 'guided_evidence_resolution',
      property_id: 'p1',
      metadata: {
        take_action: {
          primary: {
            kind: 'direct_evidence_action',
            property_id: 'p1',
            requirement_id: 'r1',
            evidence_mode: 'STRUCTURED_DECLARATION',
            label: 'Submit compliance declaration',
          },
        },
      },
    };
    const cta = resolveTaskCta(task, 'primary');
    expect(cta.guidedEvidence).toEqual({
      propertyId: 'p1',
      requirementId: 'r1',
      initialEvidenceMode: 'STRUCTURED_DECLARATION',
    });
  });

  it('does not attach guidedEvidence for normal upload tasks', () => {
    const task = {
      source_type: 'requirement',
      primary_action_type: 'upload_evidence',
      property_id: 'p1',
      metadata: {
        take_action: {
          primary: {
            label: 'Upload',
            route: '/documents?property_id=p1&requirement_id=r1',
            kind: 'navigate',
            handler: 'navigate',
          },
        },
      },
    };
    const cta = resolveTaskCta(task, 'primary');
    expect(cta.guidedEvidence).toBeNull();
    expect(cta.route).toContain('/documents');
  });
});
