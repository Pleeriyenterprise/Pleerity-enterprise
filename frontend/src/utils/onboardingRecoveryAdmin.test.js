import {
  classificationLabel,
  classificationDescription,
  recoveryModeLabel,
  shouldShowOnboardingRecoveryAssessment,
} from './onboardingRecoveryAdmin';

describe('onboardingRecoveryAdmin', () => {
  it('maps classification labels', () => {
    expect(classificationLabel('PAYMENT_ABANDONED')).toBe('Payment abandoned');
    expect(classificationLabel(null)).toBe('No recovery needed');
  });

  it('describes classifications without engineering jargon', () => {
    const desc = classificationDescription('ACTIVATION_INCOMPLETE');
    expect(desc.toLowerCase()).not.toContain('stripe');
    expect(desc.length).toBeGreaterThan(10);
  });

  it('maps recovery modes', () => {
    expect(recoveryModeLabel('regenerate_payment')).toBe('Generate recovery checkout');
    expect(recoveryModeLabel('release_and_restart')).toBe('Release and restart onboarding');
  });

  it('shows assessment when stranded', () => {
    expect(
      shouldShowOnboardingRecoveryAssessment({ found: true, is_stranded: true, classification: 'PAYMENT_ABANDONED' }),
    ).toBe(true);
    expect(shouldShowOnboardingRecoveryAssessment({ found: true, is_stranded: false, classification: null })).toBe(false);
  });
});
