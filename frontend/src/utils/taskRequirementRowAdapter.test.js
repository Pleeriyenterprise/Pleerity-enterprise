import { buildRequirementShapedRowFromPriorityTask } from './taskRequirementRowAdapter';

describe('buildRequirementShapedRowFromPriorityTask', () => {
  const baseReqTask = {
    id: 'task-1',
    source_type: 'requirement',
    source_id: 'r99',
    property_id: 'p1',
    requirement_id: 'r99',
    metadata: {
      take_action: {
        primary: {
          label: 'Record evidence',
          kind: 'guided_evidence_resolution',
          handler: 'guided_evidence',
          property_id: 'p1',
          requirement_id: 'r99',
        },
      },
      requirement_code: 'gas_safety',
    },
  };

  it('returns null for non-requirement source_type', () => {
    expect(
      buildRequirementShapedRowFromPriorityTask(
        { ...baseReqTask, source_type: 'work_order', metadata: baseReqTask.metadata },
        null,
      ),
    ).toBeNull();
  });

  it('returns null when metadata.take_action is missing', () => {
    expect(
      buildRequirementShapedRowFromPriorityTask({ ...baseReqTask, metadata: {} }, null),
    ).toBeNull();
  });

  it('returns null when property_id is missing', () => {
    expect(
      buildRequirementShapedRowFromPriorityTask({ ...baseReqTask, property_id: null }, null),
    ).toBeNull();
  });

  it('returns null when requirement_id cannot be resolved', () => {
    expect(
      buildRequirementShapedRowFromPriorityTask(
        {
          ...baseReqTask,
          requirement_id: undefined,
          source_id: undefined,
          metadata: { ...baseReqTask.metadata, requirement_id: undefined },
        },
        null,
      ),
    ).toBeNull();
  });

  it('builds minimal requirement-shaped row when map is empty', () => {
    const row = buildRequirementShapedRowFromPriorityTask(baseReqTask, new Map());
    expect(row).toMatchObject({
      requirement_id: 'r99',
      property_id: 'p1',
      requirement_code: 'gas_safety',
    });
    expect(row.take_action).toBe(baseReqTask.metadata.take_action);
  });

  it('merges full requirement row from map under task take_action', () => {
    const full = {
      requirement_id: 'r99',
      property_id: 'p1',
      status: 'MISSING',
      requirement_code: 'gas_safety',
      take_action: { primary: { label: 'stale' } },
    };
    const m = new Map([['r99', full]]);
    const row = buildRequirementShapedRowFromPriorityTask(baseReqTask, m);
    expect(row.status).toBe('MISSING');
    expect(row.take_action).toBe(baseReqTask.metadata.take_action);
  });
});
