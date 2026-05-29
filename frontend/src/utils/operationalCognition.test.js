import { getListGuidance } from './operationalCognition';

describe('operationalCognition getListGuidance', () => {
  it('prefers server list_guidance over fallbacks', () => {
    const entity = {
      operational_cognition: {
        list_guidance: {
          recommended_action_label: 'Upload valid evidence document',
          cognition_version: 'operational_cognition_v1',
        },
      },
      take_action: { primary: { label: 'Client invented label' } },
      business_actions: [{ label: 'Another label', primary: true }],
    };
    expect(getListGuidance(entity).recommended_action_label).toBe('Upload valid evidence document');
  });

  it('falls back to take_action.primary when list_guidance absent', () => {
    const entity = {
      take_action: { primary: { label: 'Record payment', continuation: true } },
    };
    const g = getListGuidance(entity);
    expect(g.recommended_action_label).toBe('Record payment');
    expect(g.continuation_summary).toBe('CONTINUATION');
    expect(g.cognition_version).toBe('take_action');
  });

  it('falls back to business_actions when no cognition or take_action', () => {
    const entity = {
      business_actions: [{ label: 'View work order', primary: true }],
    };
    const g = getListGuidance(entity);
    expect(g.recommended_action_label).toBe('View work order');
    expect(g.cognition_version).toBe('business_actions');
  });

  it('returns null when no server action authority present', () => {
    expect(getListGuidance({})).toBeNull();
    expect(getListGuidance(null)).toBeNull();
  });
});
