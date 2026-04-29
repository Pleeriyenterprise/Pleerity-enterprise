/**
 * Shared support-readable labels for audit / timeline event types.
 * Raw machine values stay available for expandable details.
 */

const AUDIT_LABEL_MAP = {
  USER_LOGIN_SUCCESS: 'User signed in',
  USER_LOGIN_FAILED: 'Sign-in failed',
  USER_AUTHENTICATED_POST_SETUP: 'User authenticated after setup',
  ADMIN_LOGIN_SUCCESS: 'Admin signed in',
  ADMIN_LOGIN_FAILED: 'Admin sign-in failed',
  ADMIN_ACTION: 'Admin operation performed',
  INTAKE_SUBMITTED: 'Intake submitted',
  PROVISIONING_STARTED: 'Provisioning started',
  PROVISIONING_COMPLETE: 'Provisioning completed',
  PROVISIONING_FAILED: 'Provisioning failed',
  PORTAL_INVITE_EMAIL_FAILED: 'Portal invite email failed',
  PORTAL_INVITE_RESENT: 'Portal invite resent',
  ACTIVATION_EMAIL_SENT: 'Activation email sent',
  ACTIVATION_EMAIL_FAILED: 'Activation email failed',
  ACTIVATION_EMAIL_RESEND: 'Activation email resent',
  PASSWORD_TOKEN_GENERATED: 'Password setup token generated',
  PASSWORD_SET_SUCCESS: 'Password set successfully',
  PASSWORD_SETUP_LINK_RESENT: 'Password setup link resent',
  EMAIL_SENT: 'Email sent',
  EMAIL_FAILED: 'Email failed',
  EMAIL_SKIPPED_NO_RECIPIENT: 'Email skipped (no recipient)',
  NOTIFICATION_BLOCKED_PROVISIONING_INCOMPLETE: 'Notification blocked — provisioning incomplete',
  NOTIFICATION_BLOCKED_SUBSCRIPTION_INACTIVE: 'Notification blocked — subscription inactive',
  NOTIFICATION_BLOCKED_PLAN_GATE: 'Notification blocked — plan gate',
  NOTIFICATION_BLOCKED_PREFERENCE_DISABLED: 'Notification blocked — preference disabled',
  NOTIFICATION_PROVIDER_NOT_CONFIGURED: 'Notification provider not configured',
  NOTIFICATION_FAILED_PERMANENT: 'Notification failed permanently',
  NOTIFICATION_THROTTLED: 'Notification throttled',
  NOTIFICATION_FAILURE_SPIKE_DETECTED: 'Notification failure spike detected',
  RATE_LIMIT_EXCEEDED: 'Rate limit exceeded',
  COMPLIANCE_STATUS_UPDATED: 'Compliance status updated',
  COMPLIANCE_SCORE_UPDATED: 'Compliance score updated',
  SESSION_FORCE_LOGOUT: 'Sessions invalidated (force logout)',
};

function notificationBlockedLabel(action) {
  const a = String(action || '');
  if (!a.startsWith('NOTIFICATION_BLOCKED_')) return null;
  const tail = a.replace(/^NOTIFICATION_BLOCKED_/, '').replace(/_/g, ' ').toLowerCase();
  return `Notification blocked — ${tail}`;
}

/**
 * @param {string | null | undefined} action
 * @returns {string}
 */
export function getAuditEventLabel(action) {
  const key = String(action || '').trim();
  if (!key) return 'Unknown event';
  if (AUDIT_LABEL_MAP[key]) return AUDIT_LABEL_MAP[key];
  const nb = notificationBlockedLabel(key);
  if (nb) return nb;
  return key
    .split('_')
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(' ');
}

/**
 * @param {string | null | undefined} action
 * @returns {'info' | 'low' | 'medium' | 'high' | 'critical'}
 */
export function getAuditEventSeverity(action) {
  const a = String(action || '').toUpperCase();
  if (!a) return 'info';
  if (a.includes('FAILED') || a.includes('BLOCKED') || a.includes('SPIKE') || a.includes('BOUNCED')) return 'high';
  if (a.includes('SUCCESS') || a.includes('COMPLETE') || a.includes('SENT') || a.includes('DELIVERED')) return 'low';
  if (a.includes('ADMIN_ACTION') || a.includes('PASSWORD') || a.includes('PROVISIONING')) return 'medium';
  if (a.includes('DELETED') || a.includes('PERMANENT') || a.includes('BREAK_GLASS')) return 'critical';
  return 'info';
}

const SEVERITY_BADGE_CLASS = {
  info: 'bg-slate-100 text-slate-800',
  low: 'bg-emerald-100 text-emerald-900',
  medium: 'bg-amber-100 text-amber-900',
  high: 'bg-red-100 text-red-900',
  critical: 'bg-red-700 text-white',
};

export function getAuditSeverityBadgeClass(severity) {
  return SEVERITY_BADGE_CLASS[severity] || SEVERITY_BADGE_CLASS.info;
}

/**
 * @param {string | number | Date | null | undefined} value
 * @returns {string}
 */
export function formatAuditTimestampUtc(value) {
  if (value == null || value === '') return '—';
  try {
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString('en-GB', {
      timeZone: 'UTC',
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
      .replace(',', '')
      .concat(' UTC');
  } catch {
    return '—';
  }
}
