import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'PropertiesPage.js');

describe('PropertiesPage capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/usePropertyCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it('gates portfolio list and create on property capability flags', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canViewProperties/);
    expect(src).toMatch(/canCreateProperty/);
    expect(src).toMatch(/isCapabilityDeniedApiError/);
  });
});
