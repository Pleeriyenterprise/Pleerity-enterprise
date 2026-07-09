import fs from 'fs';
import path from 'path';

const CUSTOMER_PAGES = [
  'ComplianceScorePage.js',
  'IntegrationsPage.js',
  'ClientRentOperationsPage.js',
  'ClientTenantComplianceDeliveryPage.js',
  'CalendarPage.js',
  'AssistantPage.js',
  'IntakePage.js',
];

const SHARED = [
  '../components/UpgradePrompt.js',
  '../components/client/PlanRestrictedActionModal.jsx',
  '../utils/EntitlementProtectedRoute.js',
  '../App.js',
];

describe('ILP-4 final customer authority migration', () => {
  it.each(CUSTOMER_PAGES)('pages/%s avoids legacy entitlement permission hooks', (file) => {
    const src = fs.readFileSync(path.join(__dirname, file), 'utf8');
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it.each(SHARED)('%s avoids useEntitlements for customer permission', (file) => {
    const src = fs.readFileSync(path.join(__dirname, file), 'utf8');
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
  });

  it('App.js does not mount EntitlementsProvider', () => {
    const src = fs.readFileSync(path.join(__dirname, '../App.js'), 'utf8');
    expect(src).not.toMatch(/EntitlementsProvider/);
    expect(src).toMatch(/AccountCapabilityProtectedRoute/);
  });

  it('EntitlementProtectedRoute is compatibility re-export only', () => {
    const src = fs.readFileSync(path.join(__dirname, '../utils/EntitlementProtectedRoute.js'), 'utf8');
    expect(src).toMatch(/AccountCapabilityProtectedRoute/);
    expect(src).not.toMatch(/useEntitlements/);
  });
});
