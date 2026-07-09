import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'ClientCommandCenterPage.js');

describe('ClientCommandCenterPage capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/useCommandCentreCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it('gates command centre and ops widgets on runtime capability flags', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canViewCommandCentre/);
    expect(src).toMatch(/canUseOpsMaintenance/);
    expect(src).toMatch(/canUseOpsPredictive/);
    expect(src).toMatch(/isCapabilityDeniedApiError/);
  });
});
