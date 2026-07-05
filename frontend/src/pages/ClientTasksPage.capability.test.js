import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'ClientTasksPage.js');

describe('ClientTasksPage capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/useTodayCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it('gates today read and write actions on runtime capability flags', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canViewToday/);
    expect(src).toMatch(/canActToday/);
    expect(src).toMatch(/canUseOpsMaintenance/);
    expect(src).toMatch(/canUseOpsPredictive/);
    expect(src).toMatch(/canUseOpsApprovals/);
    expect(src).toMatch(/isCapabilityDeniedApiError/);
  });
});
