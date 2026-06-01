/** Admin labels for onboarding recovery classifications (Phase 1). */

export const ONBOARDING_RECOVERY_CLASSIFICATIONS = {
  PAYMENT_ABANDONED: {
    label: 'Payment abandoned',
    description: 'Intake is complete but subscription payment has not been completed.',
  },
  EXPIRED_CHECKOUT: {
    label: 'Expired checkout',
    description: 'A previous payment link is no longer valid.',
  },
  PROMO_REDEMPTION_FAILED: {
    label: 'Promo redemption failed',
    description: 'Promo redemption did not complete payment successfully.',
  },
  FIRST_TIME_RESTRICTION_COLLISION: {
    label: 'First-time restriction',
    description: 'Promo first-time rules are blocking a retry.',
  },
  PARTIAL_PROVISIONING: {
    label: 'Partial provisioning',
    description: 'Provisioning did not complete after payment.',
  },
  ACTIVATION_INCOMPLETE: {
    label: 'Activation incomplete',
    description: 'Subscription is active but portal activation is incomplete.',
  },
  SUBSCRIPTION_DRIFT: {
    label: 'Subscription drift',
    description: 'Billing records disagree with onboarding state.',
  },
  DUPLICATE_RECOVERY_RISK: {
    label: 'Duplicate recovery risk',
    description: 'Recovery signals conflict with paid or active subscription state.',
  },
  RECOVERY_ALREADY_ACTIVE: {
    label: 'Recovery already active',
    description: 'A recent recovery checkout link may still be valid.',
  },
  UNKNOWN_RECOVERY_STATE: {
    label: 'Unknown recovery state',
    description: 'Onboarding appears stranded but requires manual review.',
  },
};

export const RECOVERY_MODE_LABELS = {
  resume_onboarding: 'Resume onboarding',
  regenerate_payment: 'Generate recovery checkout',
  resend_activation: 'Resend activation',
  manual_escalation: 'Manual escalation',
};

export const RECOVERY_RISK_BADGE_CLASS = {
  low: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  medium: 'bg-amber-50 text-amber-950 border-amber-200',
  high: 'bg-red-50 text-red-900 border-red-200',
};

export function classificationLabel(classification) {
  if (!classification) return 'No recovery needed';
  return ONBOARDING_RECOVERY_CLASSIFICATIONS[classification]?.label || classification;
}

export function classificationDescription(classification) {
  if (!classification) return 'Customer onboarding appears complete or not stranded.';
  return ONBOARDING_RECOVERY_CLASSIFICATIONS[classification]?.description || '';
}

export function recoveryModeLabel(mode) {
  if (!mode) return '—';
  return RECOVERY_MODE_LABELS[mode] || mode;
}

export function shouldShowOnboardingRecoveryAssessment(assessment) {
  if (!assessment?.found) return false;
  return Boolean(assessment.is_stranded || assessment.classification);
}
