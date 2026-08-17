import fs from 'fs';
import path from 'path';

const controlsPath = path.join(__dirname, 'CommercialEntitlementControls.jsx');
const dialogPath = path.join(__dirname, 'CommercialEntitlementExecuteDialog.jsx');
const pagePath = path.join(__dirname, '../../../pages/AdminClientControlPanelPage.js');
const utilPath = path.join(__dirname, '../../../utils/commercialEntitlementAdmin.js');

describe('CommercialEntitlementControls submission lifecycle', () => {
  it('renders the step-up password modal host (indefinite spinner root cause)', () => {
    const src = fs.readFileSync(controlsPath, 'utf8');
    expect(src).toMatch(/stepUp\.modal/);
    expect(src).toMatch(/commercial-step-up-modal-host/);
    expect(src).toMatch(/timeout:\s*60000/);
    expect(src).toMatch(/onExecuted/);
  });

  it('renders effective access and restored plan separately from canonical access', () => {
    const src = fs.readFileSync(controlsPath, 'utf8');
    expect(src).toMatch(/commercial-effective-access/);
    expect(src).toMatch(/commercial-restored-plan/);
    expect(src).toMatch(/effective_entitlement_state/);
    expect(src).toMatch(/restored_plan_code/);
  });

  it('does not toast success when customer email was requested but not confirmed', () => {
    const src = fs.readFileSync(controlsPath, 'utf8');
    expect(src).toMatch(/send_customer_email/);
    expect(src).toMatch(/toast\.warning/);
    expect(src).toMatch(/customer email was not confirmed/);
  });
});

describe('CommercialEntitlementExecuteDialog', () => {
  it('caps duration per action and terminates spinner on timeout', () => {
    const src = fs.readFileSync(dialogPath, 'utf8');
    expect(src).toMatch(/ACTION_DURATION_MAX_DAYS/);
    expect(src).toMatch(/ECONNABORTED/);
    expect(src).toMatch(/do not assume success/);
    expect(src).toMatch(/if \(loading && !v\) return/);
    expect(src).toMatch(/if \(loading\) return/);
    expect(src).toMatch(/commercial-execute-submit/);
  });
});

describe('AdminClientControlPanel refresh after commercial execute', () => {
  it('silently reloads billing surfaces after a commercial action', () => {
    const src = fs.readFileSync(pagePath, 'utf8');
    expect(src).toMatch(/onExecuted=\{\(\) => loadPanel\(\{ silent: true \}\)\}/);
    expect(src).toMatch(/opts\.silent/);
  });
});

describe('commercialEntitlementAdmin duration caps', () => {
  it('keeps UI duration caps aligned with backend maxima', () => {
    const src = fs.readFileSync(utilPath, 'utf8');
    expect(src).toMatch(/grant_grace_period:\s*30/);
    expect(src).toMatch(/suspend_billing:\s*90/);
    expect(src).toMatch(/COMMERCIAL_EXECUTE_TIMEOUT_MS\s*=\s*60000/);
  });
});
