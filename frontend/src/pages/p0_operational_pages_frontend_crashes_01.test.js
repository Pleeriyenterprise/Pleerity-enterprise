/**
 * P0-OPERATIONAL-PAGES-FRONTEND-CRASHES-01 — static wiring guards for operational pages.
 */
import fs from 'fs';
import path from 'path';

const OPERATIONAL_PAGES = [
  'ClientMaintenancePage.js',
  'ClientJobDetailPage.js',
  'ClientIssuesPage.js',
  'ClientIssueDetailPage.js',
  'ClientRiskSignalsPage.js',
  'ClientContractorsPage.js',
  'ClientApprovalsPage.js',
];

function readPage(file) {
  return fs.readFileSync(path.join(__dirname, file), 'utf8');
}

describe('P0 operational pages frontend crash guards', () => {
  it.each(OPERATIONAL_PAGES)('%s uses runtime contract capability helpers', (file) => {
    const src = readPage(file);
    expect(src).toMatch(/useOperationalExecutionCapabilities|OperationalCapabilityProtectedRoute/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/EntitlementProtectedRoute/);
  });

  it.each(OPERATIONAL_PAGES)('%s imports ContractorNetworkLockedModal when rendered', (file) => {
    const src = readPage(file);
    if (!src.includes('<ContractorNetworkLockedModal')) return;
    expect(src).toMatch(/import\s*\{[^}]*ContractorNetworkLockedModal[^}]*\}\s*from/);
  });

  it('ClientIssuesPage imports ContractorNetworkLockedModal', () => {
    const src = readPage('ClientIssuesPage.js');
    expect(src).toMatch(/import\s*\{[^}]*ContractorNetworkLockedModal/);
    expect(src).toMatch(/<ContractorNetworkLockedModal/);
  });

  it('ClientApprovalsPage wires approvalsStepUp via useStepUpApi', () => {
    const src = readPage('ClientApprovalsPage.js');
    expect(src).toMatch(/import\s*\{[^}]*useStepUpApi[^}]*\}\s*from\s*['"]\.\.\/hooks\/useStepUpApi['"]/);
    expect(src).toMatch(/const approvalsStepUp = useStepUpApi\(\)/);
    expect(src).toMatch(/approvalsStepUp[\s\S]*?\.request\(/);
    expect(src).toMatch(/\{approvalsStepUp\.modal\}/);
  });

  it.each(OPERATIONAL_PAGES)('%s imports toast when toast helpers are used', (file) => {
    const src = readPage(file);
    if (!src.match(/\btoast\.(success|error|info|warning)\(/)) return;
    expect(src).toMatch(/import\s*\{[^}]*toast[^}]*\}\s*from/);
  });
});
