import {
  alignProgressTrackerWithContractorFacts,
  clientJobProgressFromJob,
  deriveCanonicalJobStatus,
  progressTrackerFromContract,
} from './jobWorkflowUi';

describe('jobWorkflowUi progress alignment', () => {
  it('corrects assigned complete without contractor_id', () => {
    const job = {
      contractor_id: '',
      status: 'ASSIGNED',
      progress_contract: {
        progress_steps: [
          { key: 'assigned', label: 'Contractor assigned', state: 'complete' },
          { key: 'quote_submitted', label: 'Quote submitted', state: 'current' },
        ],
      },
    };
    const tracker = progressTrackerFromContract(job);
    expect(tracker.progressDriftCorrected).toBe(true);
    expect(tracker.steps[0]).toBe('Awaiting contractor assignment');
    expect(tracker.completedFlags[0]).toBe(false);
  });

  it('keeps contractor assigned when contractor_id present', () => {
    const job = {
      contractor_id: 'c-1',
      progress_contract: {
        progress_steps: [
          { key: 'assigned', label: 'Contractor assigned', state: 'complete' },
          { key: 'visit_booked', label: 'Visit booked', state: 'current' },
        ],
      },
    };
    const tracker = clientJobProgressFromJob(job);
    expect(tracker.steps[0]).toBe('Contractor assigned');
    expect(tracker.progressDriftCorrected).toBeUndefined();
  });

  it('alignProgressTrackerWithContractorFacts is a no-op when facts match', () => {
    const job = { contractor_id: 'c-1' };
    const base = {
      steps: ['Contractor assigned', 'Visit booked'],
      currentIndex: 1,
      completedFlags: [true, false],
      progressContract: {
        progress_steps: [
          { key: 'assigned', label: 'Contractor assigned', state: 'complete' },
          { key: 'visit_booked', label: 'Visit booked', state: 'current' },
        ],
      },
    };
    expect(alignProgressTrackerWithContractorFacts(job, base)).toBe(base);
  });

  it('does not present Visit booked without a confirmed scheduled visit', () => {
    const job = {
      contractor_id: 'c-1',
      schedule_status: '',
      scheduled_at: '',
      progress_contract: {
        progress_steps: [
          { key: 'assigned', label: 'Contractor assigned', state: 'complete' },
          { key: 'visit_booked', label: 'Visit booked', state: 'current' },
        ],
      },
    };
    const tracker = progressTrackerFromContract(job);
    expect(tracker.steps[1]).toBe('Schedule visit');
    expect(tracker.visitDriftCorrected).toBe(true);
  });

  it('keeps Visit booked when schedule is confirmed', () => {
    const job = {
      contractor_id: 'c-1',
      schedule_status: 'confirmed',
      scheduled_at: '2026-07-01T10:00:00Z',
      progress_contract: {
        progress_steps: [
          { key: 'assigned', label: 'Contractor assigned', state: 'complete' },
          { key: 'visit_booked', label: 'Visit booked', state: 'complete' },
        ],
      },
    };
    const tracker = progressTrackerFromContract(job);
    expect(tracker.steps[1]).toBe('Visit booked');
    expect(tracker.visitDriftCorrected).toBeUndefined();
  });

  it('maps accepted-without-visit SCHEDULED status to ASSIGNED', () => {
    expect(
      deriveCanonicalJobStatus({
        work_order_kind: 'MAINTENANCE',
        status: 'SCHEDULED',
        contractor_id: 'c-1',
        schedule_status: '',
        scheduled_at: '',
      }),
    ).toBe('ASSIGNED');
  });
});
