import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'ReportsPage.js');
const AUDIT_PAGE = path.join(__dirname, 'ReportsAuditPackPage.js');

describe('Reports capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements on ReportsPage', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/useReportCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
    expect(src).not.toMatch(/UpgradeRequired/);
    expect(src).not.toMatch(/UpgradePrompt/);
  });

  it('gates report actions on runtime capability flags', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canViewReports/);
    expect(src).toMatch(/canGeneratePdf/);
    expect(src).toMatch(/canGenerateCsv/);
    expect(src).toMatch(/canScheduleReportsWrite/);
    expect(src).toMatch(/canAuditPackRead/);
    expect(src).toMatch(/isCapabilityDeniedApiError/);
  });

  it('uses runtime contract capabilities on ReportsAuditPackPage', () => {
    const src = fs.readFileSync(AUDIT_PAGE, 'utf8');
    expect(src).toMatch(/useReportCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });
});
