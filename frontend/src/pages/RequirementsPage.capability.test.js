import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'RequirementsPage.js');

describe('RequirementsPage capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/usePropertyWorkflowCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it('gates requirement actions on runtime capability flags', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canViewRequirements/);
    expect(src).toMatch(/canResolveRequirements/);
    expect(src).toMatch(/canMarkRequirementNotApplicable/);
    expect(src).toMatch(/isCapabilityDeniedApiError/);
  });
});
