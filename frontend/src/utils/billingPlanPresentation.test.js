import {
  BILLING_PLAN_FEATURE_MATRIX,
  featureCountForPlanBanner,
  isFeatureEnabledForBillingComparison,
  planPropertyLimitForDisplay,
} from './billingPlanPresentation';

describe('billingPlanPresentation', () => {
  it('uses static plan matrix for feature comparison (no entitlements)', () => {
    expect(isFeatureEnabledForBillingComparison('PLAN_1_SOLO', 'webhooks')).toBe(false);
    expect(isFeatureEnabledForBillingComparison('PLAN_3_PRO', 'webhooks')).toBe(true);
    expect(isFeatureEnabledForBillingComparison('PLAN_UNKNOWN', 'webhooks')).toBe(false);
  });

  it('counts enabled features per plan tier from static matrix', () => {
    expect(featureCountForPlanBanner('PLAN_1_SOLO')).toBe(
      Object.values(BILLING_PLAN_FEATURE_MATRIX.PLAN_1_SOLO).filter(Boolean).length,
    );
    expect(featureCountForPlanBanner('PLAN_3_PRO')).toBe(
      Object.values(BILLING_PLAN_FEATURE_MATRIX.PLAN_3_PRO).filter(Boolean).length,
    );
  });

  it('prefers billing status property limit for banner display', () => {
    const plans = [{ code: 'PLAN_2_PORTFOLIO', maxProperties: 10 }];
    expect(
      planPropertyLimitForDisplay('PLAN_2_PORTFOLIO', { properties_limit: 8 }, plans),
    ).toBe(8);
    expect(planPropertyLimitForDisplay('PLAN_2_PORTFOLIO', {}, plans)).toBe(10);
  });
});
