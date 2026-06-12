import { isIssueAssignContractorLocked } from './contractorNetworkEntitlement';

describe('contractorNetworkEntitlement', () => {
  const assignPrimary = { key: 'assign_contractor', label: 'Assign contractor', url: '/operations/jobs/abc' };

  it('locks assign contractor when contractor_network is off', () => {
    expect(isIssueAssignContractorLocked(assignPrimary, false)).toBe(true);
  });

  it('does not lock when contractor_network is on', () => {
    expect(isIssueAssignContractorLocked(assignPrimary, true)).toBe(false);
  });

  it('does not lock unrelated primary actions', () => {
    expect(isIssueAssignContractorLocked({ key: 'maintenance_job', label: 'Create job' }, false)).toBe(false);
  });
});
