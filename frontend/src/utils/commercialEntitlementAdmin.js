const ACTION_LABELS = {
  grant_grace_period: 'Grant grace period',
  suspend_billing: 'Suspend billing',
  resume_billing: 'Resume billing',
  grant_sponsored_access: 'Sponsored access',
  retention_extension: 'Retention extension',
  waive_onboarding_fee: 'Waive onboarding fee',
  apply_recovery_compensation: 'Recovery compensation',
  restrict_entitlement: 'Restrict entitlement',
  revoke_commercial_exception: 'Revoke exception',
};

export function commercialActionLabel(action) {
  return ACTION_LABELS[action] || action || '—';
}

export const COMMERCIAL_RISK_BADGE_CLASS = {
  low: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  medium: 'border-amber-200 bg-amber-50 text-amber-900',
  high: 'border-red-200 bg-red-50 text-red-900',
};
