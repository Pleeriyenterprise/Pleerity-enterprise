import {
  BILLING_CAPABILITY,
  BILLING_LIFECYCLE_GRANT_FIXTURES,
  evaluateBillingCapabilitiesFromMap,
  formatBillingUsageHint,
  getCapabilityDeniedMessage,
  isCapabilityDeniedApiError,
} from './billingCapabilityAccess';

describe('billingCapabilityAccess', () => {
  it('formats usage hint from billing status fields', () => {
    expect(formatBillingUsageHint({ properties_used: 3, properties_limit: 10 })).toMatch(/3 properties/);
    expect(formatBillingUsageHint({ properties_used: 5, properties_limit: 5 })).toMatch(/property limit/);
  });

  it('parses capability_denied API payloads', () => {
    const error = {
      response: {
        data: {
          detail: {
            error: 'capability_denied',
            message: 'Billing checkout is not available.',
            capability_id: BILLING_CAPABILITY.CHECKOUT,
          },
        },
      },
    };
    expect(isCapabilityDeniedApiError(error)).toBe(true);
    expect(getCapabilityDeniedMessage(error)).toBe('Billing checkout is not available.');
  });

  describe.each([
    ['ACTIVE', true],
    ['TRIAL', true],
    ['GRACE_PERIOD', true],
    ['CANCELLATION_SCHEDULED', true],
    ['CANCELLED_IMMEDIATE', true],
    ['SUBSCRIPTION_EXPIRED', true],
    ['READ_ONLY', true],
    ['SUSPENDED', true],
    ['ARCHIVED', false],
    ['ACCOUNT_DELETED', false],
    ['UNKNOWN', false],
  ])('recovery lifecycle %s checkout allowed=%s', (lifecycle, checkoutAllowed) => {
    it('mirrors runtime contract billing recovery grants', () => {
      const flags = evaluateBillingCapabilitiesFromMap(BILLING_LIFECYCLE_GRANT_FIXTURES[lifecycle]);
      expect(flags.canCheckout).toBe(checkoutAllowed);
      expect(flags.canViewBilling).toBe(checkoutAllowed);
      if (checkoutAllowed) {
        expect(flags.canManageSubscription).toBe(true);
        expect(flags.canViewInvoices).toBe(true);
      }
    });
  });
});
