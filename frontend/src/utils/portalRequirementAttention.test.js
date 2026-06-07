import {
  alignTodayPayloadTaskSections,
  filterInboxTasksForOperationalActionability,
  isTaskAssuranceOnly,
} from './portalRequirementAttention';

describe('portalRequirementAttention operational actionability', () => {
  it('filterInboxTasksForOperationalActionability is defined and removes assurance-only tasks', () => {
    const reqMap = new Map([
      ['r1', { requirement_id: 'r1', client_lifecycle_state: 'SATISFIED_UNVERIFIED' }],
      ['r2', { requirement_id: 'r2', client_lifecycle_state: 'ACTION_REQUIRED' }],
    ]);
    const tasks = [
      { id: 't1', source_type: 'issue', metadata: { requirement_id: 'r1' } },
      { id: 't2', source_type: 'requirement', metadata: { requirement_id: 'r2' } },
    ];
    expect(typeof filterInboxTasksForOperationalActionability).toBe('function');
    expect(isTaskAssuranceOnly(tasks[0], reqMap)).toBe(true);
    const filtered = filterInboxTasksForOperationalActionability(tasks, reqMap);
    expect(filtered.map((t) => t.id)).toEqual(['t2']);
  });

  it('alignTodayPayloadTaskSections does not throw when urgent is empty', () => {
    const reqMap = new Map([
      ['r1', { requirement_id: 'r1', client_lifecycle_state: 'SATISFIED_UNVERIFIED' }],
    ]);
    const payload = {
      tasks: {
        urgent: [],
        upcoming: [],
        in_progress: [{ id: 't1', source_type: 'issue', metadata: { requirement_id: 'r1' } }],
        recently_completed: [],
        snoozed: [],
        hidden: [],
      },
    };
    expect(() => alignTodayPayloadTaskSections(payload, reqMap)).not.toThrow();
    const sections = alignTodayPayloadTaskSections(payload, reqMap);
    expect(sections.in_progress).toEqual([]);
    expect(sections.urgent).toEqual([]);
  });
});
