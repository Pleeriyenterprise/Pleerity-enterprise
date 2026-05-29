import {
  buildFalseEmptyStateDisclosure,
  classifyTaskOperationalBucket,
  visibleOpenCount,
} from './todayExecutionWorkspace';

describe('todayExecutionWorkspace', () => {
  it('classifies pending review requirements as waiting on others', () => {
    const reqMap = new Map([
      ['r1', { requirement_id: 'r1', client_lifecycle_state: 'PENDING_REVIEW' }],
    ]);
    const bucket = classifyTaskOperationalBucket(
      { id: 't1', source_type: 'requirement', metadata: { requirement_id: 'r1' }, section: 'urgent' },
      reqMap,
    );
    expect(bucket).toBe('waiting_on_others');
  });

  it('detects false calm when command centre has debt', () => {
    const d = buildFalseEmptyStateDisclosure({
      visibleOpenCount: 0,
      bucketContinuation: null,
      commandCenterUrgentCount: 8,
      commandCenterPrimaryCount: 0,
      propertyFilter: '',
    });
    expect(d.isFalseCalm).toBe(true);
    expect(d.message).toMatch(/Command Centre/);
  });

  it('sums visible open operational sections', () => {
    expect(
      visibleOpenCount({
        needsActionNow: [{ id: 'a' }],
        waitingOnOthers: [{ id: 'b' }],
        inProgress: [],
      }),
    ).toBe(2);
  });
});
