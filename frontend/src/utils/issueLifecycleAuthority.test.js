import {
  isOpenIssueStatus,
  isTerminalIssueStatus,
  resolvedIssueEvidenceUrl,
  TERMINAL_ISSUE_STATUSES,
} from './issueLifecycleAuthority';

describe('issueLifecycleAuthority', () => {
  it('classifies terminal statuses', () => {
    expect(isTerminalIssueStatus('resolved')).toBe(true);
    expect(isOpenIssueStatus('triaged')).toBe(true);
    expect(TERMINAL_ISSUE_STATUSES.has('cancelled')).toBe(true);
  });

  it('builds resolved evidence URL from issue metadata', () => {
    const url = resolvedIssueEvidenceUrl({
      status: 'resolved',
      resolution_linked_requirement_id: 'r1',
      resolution_linked_property_id: 'p1',
    });
    expect(url).toContain('property_id=p1');
    expect(url).toContain('requirement_id=r1');
  });

  it('returns null when resolved issue lacks linkage metadata', () => {
    expect(resolvedIssueEvidenceUrl({ status: 'resolved' })).toBeNull();
  });
});
