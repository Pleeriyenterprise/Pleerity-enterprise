/**
 * Governed customer-facing lifecycle recovery copy (mirrors backend lifecycle_recovery_customer_copy).
 * CAP_* identifiers must not appear in normal customer UI.
 */

export const PORTAL_MODE_CAPABILITY_DENIAL = {
  SUSPENDED:
    'This area is unavailable while your account is suspended. Resolve payment to restore access.',
  BILLING_RECOVERY:
    'This area is unavailable while your subscription is inactive. Resubscribe in Billing to restore access.',
  PAYMENT_REQUIRED:
    'This area is unavailable until setup is complete. Choose a plan in Billing to continue.',
  GRACE:
    'This area is unavailable until your payment issue is resolved. Update your payment method in Billing.',
  READ_ONLY: 'This area is in view-only mode. Subscribe in Billing to make changes.',
  ARCHIVED:
    'This area is unavailable while your account is archived. Contact support for assistance.',
  ACCOUNT_DELETED: 'This area is unavailable. This account has been removed.',
};

const DEFAULT_CAPABILITY_DENIAL = 'This action is not available for your account.';

const INTERNAL_CAP_MESSAGE_RE =
  /^(?:Access requires )?CAP_[A-Z0-9_]+(?: is not (?:permitted|available)(?: for your account(?: status)?)?\.?)?$/i;

export function isLifecycleRestrictedPortalMode(portalMode) {
  return Boolean(portalMode && portalMode !== 'FULL_ACCESS');
}

export function lifecycleCapabilityDenialMessage(portalMode) {
  if (!portalMode || portalMode === 'FULL_ACCESS') {
    return DEFAULT_CAPABILITY_DENIAL;
  }
  return PORTAL_MODE_CAPABILITY_DENIAL[portalMode] || DEFAULT_CAPABILITY_DENIAL;
}

export function containsInternalCapabilityLanguage(message) {
  if (message == null || message === '') return false;
  const text = String(message).trim();
  if (!text.includes('CAP_')) return false;
  return INTERNAL_CAP_MESSAGE_RE.test(text) || /\bCAP_[A-Z0-9_]+\b/.test(text);
}

/**
 * Replace backend capability denial strings that leak CAP_* ids into customer surfaces.
 * @param {unknown} message
 * @param {string | null | undefined} portalMode
 * @param {string} [fallback]
 */
export function sanitizeCapabilityCustomerMessage(message, portalMode, fallback = DEFAULT_CAPABILITY_DENIAL) {
  if (message == null || message === '') return fallback;
  const text = String(message).trim();
  if (!containsInternalCapabilityLanguage(text)) return text;
  if (isLifecycleRestrictedPortalMode(portalMode)) {
    return lifecycleCapabilityDenialMessage(portalMode);
  }
  return fallback;
}
