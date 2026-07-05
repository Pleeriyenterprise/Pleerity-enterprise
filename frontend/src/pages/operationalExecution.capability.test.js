import fs from 'fs';
import path from 'path';

const PAGES = [
  'ClientMaintenancePage.js',
  'ClientJobDetailPage.js',
  'ClientIssuesPage.js',
  'ClientIssueDetailPage.js',
  'ClientRiskSignalsPage.js',
  'ClientContractorsPage.js',
  'ClientApprovalsPage.js',
];

describe('operational execution pages capability consumption', () => {
  it.each(PAGES)('%s uses runtime contract instead of entitlements', (file) => {
    const src = fs.readFileSync(path.join(__dirname, file), 'utf8');
    expect(src).toMatch(/useOperationalExecutionCapabilities|OperationalCapabilityProtectedRoute/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
    expect(src).not.toMatch(/EntitlementProtectedRoute/);
  });
});
