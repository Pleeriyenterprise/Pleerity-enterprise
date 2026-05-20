import {
  buildOverridePayload,
  isOverrideActive,
  indicatorsToBadges,
  overrideTypeLabel,
  redemptionStatusBadgeClass,
  shouldShowRecoveryPanel,
  showAllowRetryAction,
  showResetIncompleteAction,
} from './pilotRedemptionAdmin';

describe('pilotRedemptionAdmin', () => {
  test('buildOverridePayload requires reason min length', () => {
    expect(() =>
      buildOverridePayload({
        overrideType: 'bypass_first_time',
        reason: 'ab',
        scope: 'email',
        scopeValue: 'u@example.com',
      }),
    ).toThrow(/at least 3/);
  });

  test('buildOverridePayload returns API body', () => {
    const body = buildOverridePayload({
      overrideType: 'bypass_first_time',
      reason: 'Existing customer approved',
      scope: 'client_id',
      scopeValue: 'client-1',
    });
    expect(body).toEqual({
      scope: 'client_id',
      scope_value: 'client-1',
      override_type: 'bypass_first_time',
      override_reason: 'Existing customer approved',
    });
  });

  test('showAllowRetryAction when blocked by API', () => {
    expect(showAllowRetryAction({ redemption_id: 'r1', retry_eligible: false, consumes_eligibility: false })).toBe(
      true,
    );
    expect(showAllowRetryAction({ redemption_id: 'r1', retry_eligible: true, consumes_eligibility: false })).toBe(
      false,
    );
    expect(showAllowRetryAction({ redemption_id: 'r1', retry_eligible: false, consumes_eligibility: true })).toBe(
      false,
    );
  });

  test('showResetIncompleteAction for incomplete statuses', () => {
    expect(showResetIncompleteAction({ redemption_id: 'r1', status: 'pending', consumes_eligibility: false })).toBe(
      true,
    );
    expect(showResetIncompleteAction({ redemption_id: 'r1', status: 'redeemed', consumes_eligibility: true })).toBe(
      false,
    );
  });

  test('isOverrideActive respects revoked and expiry', () => {
    expect(isOverrideActive({ override_id: '1' })).toBe(true);
    expect(isOverrideActive({ override_id: '1', revoked_at: new Date().toISOString() })).toBe(false);
    const past = new Date(Date.now() - 86400000).toISOString();
    expect(isOverrideActive({ override_id: '1', override_expires_at: past })).toBe(false);
  });

  test('overrideTypeLabel maps known types', () => {
    expect(overrideTypeLabel('bypass_first_time')).toContain('first-time');
  });

  test('redemptionStatusBadgeClass', () => {
    expect(redemptionStatusBadgeClass('payment_failed')).toContain('red');
    expect(redemptionStatusBadgeClass('redeemed')).toContain('emerald');
  });

  test('shouldShowRecoveryPanel respects API flag and fallback', () => {
    expect(shouldShowRecoveryPanel({ showRecoveryPanel: false, redemptions: [{ redemption_id: 'r1' }] })).toBe(
      false,
    );
    expect(shouldShowRecoveryPanel({ redemptions: [{ redemption_id: 'r1' }] })).toBe(true);
    expect(shouldShowRecoveryPanel({ inviteMetadata: { pilot_invite_code: 'X' } })).toBe(true);
    expect(shouldShowRecoveryPanel({})).toBe(false);
  });

  test('indicatorsToBadges adds stranded flag', () => {
    const badges = indicatorsToBadges({ stranded_onboarding: true, badges: ['payment_failed'] });
    expect(badges[0]).toBe('stranded_onboarding');
    expect(badges).toContain('payment_failed');
  });
});
