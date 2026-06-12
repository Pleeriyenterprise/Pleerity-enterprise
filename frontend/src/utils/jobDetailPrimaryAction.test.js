import {
  canExecuteAssignContractor,
  canShowCancelJob,
  executeJobDetailPrimaryIntent,
  handleAssignContractorClick,
  isAssignContractorEntitlementBlocked,
  jobDetailPrimaryIntentFromKey,
  resolveHeroPrimaryActionKey,
  resolveHeroPrimaryExecution,
  resolveJobDetailPrimaryIntent,
} from './jobDetailPrimaryAction';

describe('jobDetailPrimaryAction', () => {
  const assignJob = {
    status: 'OPEN',
    next_actions: [{ id: 'assign_contractor', label: 'Assign contractor', section: 'assignment' }],
    operational_cognition: {
      primary_action: { key: 'assign_contractor', label: 'Assign contractor', source: 'test' },
    },
  };

  it('resolves assign from operational_cognition', () => {
    expect(resolveHeroPrimaryActionKey(assignJob)).toBe('assign_contractor');
    expect(resolveJobDetailPrimaryIntent(assignJob).kind).toBe('assign_contractor');
  });

  it('maps assign alias to assign_contractor intent', () => {
    const job = {
      next_actions: [{ id: 'assign', label: 'Assign contractor' }],
      operational_cognition: { primary_action: { key: 'assign', label: 'Assign contractor' } },
    };
    expect(resolveHeroPrimaryActionKey(job)).toBe('assign_contractor');
  });

  it('routes visit scheduling keys to scroll_visit', () => {
    expect(jobDetailPrimaryIntentFromKey('confirm_visit').kind).toBe('scroll_visit');
    expect(jobDetailPrimaryIntentFromKey('propose_schedule').kind).toBe('scroll_visit');
  });

  it('blocks assign execution without contractor_network entitlement', () => {
    const exec = resolveHeroPrimaryExecution(assignJob, false);
    expect(exec.executable).toBe(false);
    expect(exec.lockedUpsell).toBe(true);
    expect(exec.blockedMessage).toMatch(/Professional/i);
    expect(isAssignContractorEntitlementBlocked(assignJob, false)).toBe(true);
  });

  it('allows assign execution with entitlement and next_actions', () => {
    const exec = resolveHeroPrimaryExecution(assignJob, true);
    expect(exec.executable).toBe(true);
    expect(canExecuteAssignContractor(assignJob, true)).toBe(true);
  });

  it('executeJobDetailPrimaryIntent opens assign modal', () => {
    const openAssignModal = jest.fn();
    executeJobDetailPrimaryIntent({ kind: 'assign_contractor', key: 'assign_contractor' }, { openAssignModal });
    expect(openAssignModal).toHaveBeenCalled();
  });

  it('executeJobDetailPrimaryIntent scrolls for confirm_visit', () => {
    const scrollToVisit = jest.fn();
    executeJobDetailPrimaryIntent({ kind: 'scroll_visit', key: 'confirm_visit' }, { scrollToVisit });
    expect(scrollToVisit).toHaveBeenCalled();
  });

  it('handleAssignContractorClick invokes onLocked without contractor_network', () => {
    const openAssignModal = jest.fn();
    const onLocked = jest.fn();
    handleAssignContractorClick(assignJob, false, openAssignModal, { onLocked });
    expect(onLocked).toHaveBeenCalled();
    expect(openAssignModal).not.toHaveBeenCalled();
  });

  it('governs cancel on next_actions cancel id', () => {
    const open = { next_actions: [{ id: 'assign_contractor', label: 'Assign' }, { id: 'cancel', label: 'Cancel job' }] };
    const closed = { status: 'CLOSED', next_actions: [{ id: 'none', label: 'Job closed' }] };
    expect(canShowCancelJob(open)).toBe(true);
    expect(canShowCancelJob(closed)).toBe(false);
  });
});
