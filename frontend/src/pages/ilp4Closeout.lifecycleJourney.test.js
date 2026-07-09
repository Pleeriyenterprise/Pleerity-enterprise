/**
 * ILP-4 closeout — lifecycle journey validation (frontend capability consumption).
 * Mirrors backend runtime matrix semantics via shared grant fixtures.
 */
import { evaluateBillingCapabilitiesFromMap, BILLING_LIFECYCLE_GRANT_FIXTURES } from '../utils/billingCapabilityAccess';
import {
  evaluateProfileCapabilitiesFromMap,
  evaluateSupportCapabilitiesFromMap,
  evaluateNavFeatureAllowedFromMap,
  ACCOUNT_LIFECYCLE_GRANT_FIXTURES,
} from '../utils/accountCapabilityAccess';
import {
  evaluatePropertyCapabilitiesFromMap,
  PROPERTY_LIFECYCLE_GRANT_FIXTURES,
} from '../utils/propertyCapabilityAccess';
import {
  evaluateOperationalExecutionCapabilitiesFromMap,
  OPERATIONAL_LIFECYCLE_GRANT_FIXTURES,
} from '../utils/operationalCapabilityAccess';

const CLOSEOUT_LIFECYCLES = [
  'ACTIVE',
  'READ_ONLY',
  'CANCELLED_IMMEDIATE',
  'SUBSCRIPTION_EXPIRED',
  'SUSPENDED',
  'ARCHIVED',
];

describe('ILP-4 closeout lifecycle journeys', () => {
  it.each(CLOSEOUT_LIFECYCLES)('%s billing recovery matrix is defined', (lifecycle) => {
    expect(BILLING_LIFECYCLE_GRANT_FIXTURES[lifecycle]).toBeDefined();
    const billing = evaluateBillingCapabilitiesFromMap(BILLING_LIFECYCLE_GRANT_FIXTURES[lifecycle]);
    expect(typeof billing.canViewBilling).toBe('boolean');
    expect(typeof billing.canCheckout).toBe('boolean');
  });

  it('ACTIVE allows create property and ops maintenance write', () => {
    const property = evaluatePropertyCapabilitiesFromMap(PROPERTY_LIFECYCLE_GRANT_FIXTURES.ACTIVE);
    const ops = evaluateOperationalExecutionCapabilitiesFromMap(OPERATIONAL_LIFECYCLE_GRANT_FIXTURES.ACTIVE);
    expect(property.canCreateProperty).toBe(true);
    expect(ops.canWriteOpsMaintenance).toBe(true);
  });

  it('READ_ONLY retains profile read and denies profile write', () => {
    const profile = evaluateProfileCapabilitiesFromMap(ACCOUNT_LIFECYCLE_GRANT_FIXTURES.READ_ONLY);
    const property = evaluatePropertyCapabilitiesFromMap(PROPERTY_LIFECYCLE_GRANT_FIXTURES.READ_ONLY);
    expect(profile.canViewProfile).toBe(true);
    expect(profile.canEditProfile).toBe(false);
    expect(property.canCreateProperty).toBe(false);
  });

  it('CANCELLED_IMMEDIATE keeps billing recovery checkout while denying ops write', () => {
    const billing = evaluateBillingCapabilitiesFromMap(BILLING_LIFECYCLE_GRANT_FIXTURES.CANCELLED_IMMEDIATE);
    const ops = evaluateOperationalExecutionCapabilitiesFromMap(OPERATIONAL_LIFECYCLE_GRANT_FIXTURES.CANCELLED_IMMEDIATE);
    expect(billing.canViewBilling).toBe(true);
    expect(billing.canCheckout).toBe(true);
    expect(ops.canWriteOpsMaintenance).toBe(false);
  });

  it('SUBSCRIPTION_EXPIRED keeps billing view for recovery', () => {
    const billing = evaluateBillingCapabilitiesFromMap(BILLING_LIFECYCLE_GRANT_FIXTURES.SUBSCRIPTION_EXPIRED);
    expect(billing.canViewBilling).toBe(true);
  });

  it('SUSPENDED denies customer support request and nav ops', () => {
    const support = evaluateSupportCapabilitiesFromMap(ACCOUNT_LIFECYCLE_GRANT_FIXTURES.SUSPENDED);
    expect(support.canAccessSupport).toBe(false);
    expect(evaluateNavFeatureAllowedFromMap(PROPERTY_LIFECYCLE_GRANT_FIXTURES.SUSPENDED, 'maintenance_workflows')).toBe(
      false,
    );
  });

  it('ARCHIVED denies billing and property mutations', () => {
    const billing = evaluateBillingCapabilitiesFromMap(BILLING_LIFECYCLE_GRANT_FIXTURES.ARCHIVED);
    const property = evaluatePropertyCapabilitiesFromMap(PROPERTY_LIFECYCLE_GRANT_FIXTURES.ARCHIVED);
    expect(billing.canViewBilling).toBe(false);
    expect(property.canCreateProperty).toBe(false);
  });
});
