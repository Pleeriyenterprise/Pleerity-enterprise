import {
  containsInternalCapabilityLanguage,
  isLifecycleRestrictedPortalMode,
  lifecycleCapabilityDenialMessage,
  sanitizeCapabilityCustomerMessage,
} from './lifecycleRecoveryCopy';

describe('lifecycleRecoveryCopy', () => {
  it('detects internal CAP language', () => {
    expect(containsInternalCapabilityLanguage('CAP_TODAY_VIEW is not permitted for your account status.')).toBe(true);
    expect(containsInternalCapabilityLanguage('Access requires CAP_DASHBOARD_VIEW on your account.')).toBe(true);
    expect(containsInternalCapabilityLanguage('Resolve payment to restore access.')).toBe(false);
  });

  it('returns suspended denial copy without CAP ids', () => {
    const msg = lifecycleCapabilityDenialMessage('SUSPENDED');
    expect(msg).toMatch(/suspended/i);
    expect(msg).toMatch(/resolve payment/i);
    expect(msg).not.toMatch(/CAP_/);
  });

  it('sanitizes legacy API capability messages for suspended accounts', () => {
    const sanitized = sanitizeCapabilityCustomerMessage(
      'CAP_PROP_VIEW is not permitted for your account status.',
      'SUSPENDED',
    );
    expect(sanitized).toBe(lifecycleCapabilityDenialMessage('SUSPENDED'));
    expect(sanitized).not.toMatch(/CAP_/);
  });

  it('leaves non-cap messages unchanged', () => {
    const original = 'Billing view is not permitted.';
    expect(sanitizeCapabilityCustomerMessage(original, 'SUSPENDED')).toBe(original);
  });

  it('marks restricted portal modes', () => {
    expect(isLifecycleRestrictedPortalMode('SUSPENDED')).toBe(true);
    expect(isLifecycleRestrictedPortalMode('FULL_ACCESS')).toBe(false);
  });
});
