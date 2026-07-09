import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'ClientDashboard.js');

describe('ClientDashboard capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/useDashboardCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it('gates dashboard and ops widgets on runtime capability flags', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canViewDashboard/);
    expect(src).toMatch(/canViewScore/);
    expect(src).toMatch(/canViewCommandCentre/);
    expect(src).toMatch(/canUseOpsMaintenance/);
    expect(src).toMatch(/canUseOpsPredictive/);
    expect(src).toMatch(/canUseOpsContractors/);
    expect(src).toMatch(/canUseOpsApprovals/);
    expect(src).toMatch(/isCapabilityDeniedApiError/);
  });
});
