/**
 * ILP-8 — consume account communication metadata from lifecycle runtime.
 * Presentation-only; does not decide permissions.
 */

/**
 * @param {object | null | undefined} runtime lifecycle_runtime payload
 * @returns {object | null}
 */
export function communicationMetadataFromRuntime(runtime) {
  if (!runtime || typeof runtime !== 'object') {
    return null;
  }
  const commPolicy = runtime.communication_policy || {};
  const cx = runtime.customer_experience || {};
  const primary = cx.primary_cta || {};
  const reactivation = runtime.reactivation_policy || {};
  return {
    lifecycle_state: runtime.lifecycle_state,
    portal_mode: runtime.portal_mode,
    message: cx.explanation || cx.heading || '',
    severity: commPolicy.template_family === 'suspended' ? 'warning' : 'info',
    cta_label: primary.label || null,
    cta_route: primary.route || null,
    template_family: commPolicy.template_family || null,
    channels: {
      email_operational: Boolean(commPolicy.email_operational),
      email_billing: Boolean(commPolicy.email_billing),
      sms: Boolean(commPolicy.sms),
      portal_notifications: Boolean(commPolicy.portal_notifications),
    },
    reactivation_eligible: Boolean(reactivation.eligible),
    reactivation_paths: Array.isArray(reactivation.paths) ? reactivation.paths : [],
  };
}
