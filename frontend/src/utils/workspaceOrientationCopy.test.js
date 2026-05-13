import {
  workspaceDashboardWelcomeLead,
  workspaceRequirementsDescriptionWindow,
  WORKSPACE_COMMAND_CENTER_PRIMARY,
} from './workspaceOrientationCopy';

describe('workspaceOrientationCopy', () => {
  it('provides dashboard welcome with fallback name', () => {
    expect(workspaceDashboardWelcomeLead('Alex')).toContain('Alex');
    expect(workspaceDashboardWelcomeLead('')).toContain('there');
  });

  it('parameterises requirements window copy', () => {
    expect(workspaceRequirementsDescriptionWindow(14)).toContain('14');
  });

  it('exports non-empty command center framing', () => {
    expect(WORKSPACE_COMMAND_CENTER_PRIMARY.length).toBeGreaterThan(40);
  });
});
