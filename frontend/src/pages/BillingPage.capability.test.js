import fs from 'fs';
import path from 'path';

const PAGE = path.join(__dirname, 'BillingPage.js');

describe('BillingPage capability consumption', () => {
  it('uses runtime contract capabilities instead of entitlements for permissions', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/useBillingCapabilities/);
    expect(src).not.toMatch(/useEntitlements/);
    expect(src).not.toMatch(/hasFeature\s*\(/);
    expect(src).not.toMatch(/UpgradeRequired/);
    expect(src).not.toMatch(/UpgradePrompt/);
    expect(src).not.toMatch(/\/client\/entitlements/);
    expect(src).not.toMatch(/\bentitlements\b/);
    expect(src).not.toMatch(/EntitlementsContext/);
    expect(src).not.toMatch(/subscription_status/);
    expect(src).not.toMatch(/entitlement_status/);
  });

  it('sources plan comparison display from presentation helpers', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/billingPlanPresentation/);
    expect(src).toMatch(/isFeatureEnabledForBillingComparison/);
    expect(src).toMatch(/featureCountForPlanBanner/);
  });

  it('gates billing actions on runtime capability flags', () => {
    const src = fs.readFileSync(PAGE, 'utf8');
    expect(src).toMatch(/canViewBilling/);
    expect(src).toMatch(/canViewInvoices/);
    expect(src).toMatch(/canViewPaymentMethods/);
    expect(src).toMatch(/canCheckout/);
    expect(src).toMatch(/canManageSubscription/);
    expect(src).toMatch(/canCancelSubscription/);
    expect(src).toMatch(/isCapabilityDeniedApiError/);
    expect(src).toMatch(/checkout_url/);
    expect(src).toMatch(/recovery_guidance/);
  });
});
