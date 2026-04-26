import { commandCenterRequirementIntelContext } from './clientCommandCenter';

describe('commandCenterRequirementIntelContext', () => {
  const byId = new Map([
    [
      'req-1',
      {
        requirement_id: 'req-1',
        display_label: 'Gas safety',
        property_jurisdiction: 'England',
      },
    ],
  ]);

  it('opens intel when a stable requirement_id is present', () => {
    const task = {
      id: 'requirement:req-1',
      source_type: 'requirement',
      source_id: 'req-1',
      property_id: 'prop-1',
      requirement_id: 'req-1',
      jurisdiction: 'England',
      title: 'Gas safety overdue',
    };
    const ctx = commandCenterRequirementIntelContext(task, byId);
    expect(ctx.canOpen).toBe(true);
    expect(ctx.requirementId).toBe('req-1');
    expect(ctx.seed.display_label).toBe('Gas safety');
    expect(ctx.seed.property_jurisdiction).toBe('England');
  });

  it('does not fabricate an id when requirement-backed task has no stable link', () => {
    const task = {
      id: 'requirement:orphan',
      source_type: 'requirement',
      source_id: '',
      property_id: 'prop-1',
      title: 'Broken row',
    };
    const ctx = commandCenterRequirementIntelContext(task, byId);
    expect(ctx.canOpen).toBe(false);
    expect(ctx.fallbackHint).toMatch(/no linked requirement id/i);
  });
});
