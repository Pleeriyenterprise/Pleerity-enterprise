/** Labels and helpers for admin pilot redemption recovery UI (display only — eligibility from API). */

export const PILOT_REDEMPTION_STATUSES = [
  'pending',
  'payment_started',
  'payment_failed',
  'provisioning_failed',
  'redeemed',
  'expired',
  'revoked',
];

export const ELIGIBILITY_OVERRIDE_TYPES = [
  { value: 'bypass_first_time', label: 'Bypass first-time restriction', description: 'Grant promo eligibility for an existing user without changing the campaign.' },
  { value: 'allow_promo_retry', label: 'Allow promo retry', description: 'Permit another redemption attempt after a failed/incomplete attempt.' },
  { value: 'manual_attach_promo', label: 'Manual attach promo', description: 'Controlled exception to attach promo benefits manually.' },
  { value: 'recover_onboarding', label: 'Recover onboarding', description: 'Recover onboarding fee / provisioning path for this identity.' },
];

export const OVERRIDE_SCOPE_OPTIONS = [
  { value: 'client_id', label: 'Client account' },
  { value: 'email', label: 'Email' },
  { value: 'invite_code_id', label: 'Invite (this code only)' },
];

export function redemptionStatusBadgeClass(status) {
  const s = String(status || '').toLowerCase();
  if (s === 'redeemed' || s === 'completed') return 'bg-emerald-100 text-emerald-800';
  if (s === 'payment_failed' || s === 'provisioning_failed') return 'bg-red-100 text-red-800';
  if (s === 'pending' || s === 'payment_started') return 'bg-amber-100 text-amber-800';
  if (s === 'expired' || s === 'revoked') return 'bg-slate-100 text-slate-700';
  return 'bg-gray-100 text-gray-700';
}

export function overrideTypeLabel(type) {
  return ELIGIBILITY_OVERRIDE_TYPES.find((t) => t.value === type)?.label || type || '—';
}

export function buildOverridePayload({ overrideType, reason, scope, scopeValue, expiresAt }) {
  const trimmed = (reason || '').trim();
  if (trimmed.length < 3) {
    throw new Error('Reason must be at least 3 characters');
  }
  if (!overrideType) {
    throw new Error('Override type is required');
  }
  if (!scopeValue?.trim()) {
    throw new Error('Scope value is required');
  }
  const body = {
    scope,
    scope_value: scopeValue.trim(),
    override_type: overrideType,
    override_reason: trimmed,
  };
  if (expiresAt) {
    body.override_expires_at = new Date(expiresAt).toISOString();
  }
  return body;
}

export function canResetIncomplete(redemption) {
  if (!redemption?.redemption_id) return false;
  const st = String(redemption.status || '').toLowerCase();
  return st !== 'redeemed' && st !== 'completed' && redemption.retry_eligible !== false;
}

/** User is blocked from retrying without admin release (retry_eligible=false from API). */
export function showAllowRetryAction(redemption) {
  if (!redemption?.redemption_id || redemption.consumes_eligibility) return false;
  return redemption.retry_eligible === false;
}

export function showResetIncompleteAction(redemption) {
  if (!redemption?.redemption_id || redemption.consumes_eligibility) return false;
  const st = String(redemption.status || '').toLowerCase();
  return st === 'pending' || st === 'payment_started' || st === 'payment_failed' || st === 'provisioning_failed';
}

export function isOverrideActive(override) {
  if (!override || override.revoked_at) return false;
  if (!override.override_expires_at) return true;
  try {
    return new Date(override.override_expires_at) > new Date();
  } catch {
    return true;
  }
}

/** Badge labels for API indicator keys (display only). */
export const RECOVERY_BADGE_LABELS = {
  payment_failed: 'Payment failed',
  provisioning_failed: 'Provisioning failed',
  incomplete_redemption: 'Incomplete redemption',
  retry_blocked: 'Retry blocked',
  override_active: 'Override active',
  first_time_bypass: 'First-time bypass',
  intake_pending: 'Intake pending',
  pending_in_grace: 'Pending (grace)',
  stranded_onboarding: 'Stranded onboarding',
  waiver_active: 'Waiver active',
  no_subscription: 'No subscription',
  retry_eligible: 'Retry eligible',
  onboarding_recovery_needed: 'Onboarding recovery needed',
};

export function recoveryBadgeLabel(key) {
  return RECOVERY_BADGE_LABELS[key] || key || '—';
}

/**
 * Whether recovery panel should render (prefer API show_recovery_panel; fallback for tests).
 */
export function shouldShowRecoveryPanel({
  showRecoveryPanel,
  redemptions = [],
  eligibilityOverrides = [],
  inviteMetadata = {},
} = {}) {
  if (showRecoveryPanel === true) return true;
  if (showRecoveryPanel === false) return false;
  if (redemptions.length > 0 || eligibilityOverrides.length > 0) return true;
  if (inviteMetadata?.pilot_invite_code || inviteMetadata?.pilot_redeemed_campaign_snapshot_id) {
    return true;
  }
  return false;
}

export function indicatorsToBadges(indicators) {
  if (!indicators) return [];
  const fromApi = Array.isArray(indicators.badges) ? [...indicators.badges] : [];
  if (indicators.stranded_onboarding && !fromApi.includes('stranded_onboarding')) {
    fromApi.unshift('stranded_onboarding');
  }
  return fromApi;
}
