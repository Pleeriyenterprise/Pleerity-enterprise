/**
 * Runtime Contract capability primitives (ILP-4 frontend foundation).
 * Mirrors backend grant semantics in account_capability_enforcement.py — no legacy inference.
 */

import { sanitizeCapabilityCustomerMessage } from './lifecycleRecoveryCopy';

export const GRANT_ALLOW = 'ALLOW';
export const GRANT_READ = 'READ';
export const GRANT_DENY = 'DENY';
export const GRANT_HIDDEN = 'HIDDEN';
export const GRANT_PLAN_GATED = 'PLAN_GATED';
export const GRANT_LIMITED = 'LIMITED';

export const SEMANTIC_READ_ONLY = 'READ_ONLY';

export const CAPABILITY_DENIED_ERROR = 'capability_denied';

/** @typedef {'read' | 'write'} CapabilityAction */

/**
 * @param {string | null | undefined} grant
 * @returns {string}
 */
export function normalizeGrantSemantic(grant) {
  if (grant === GRANT_READ) {
    return SEMANTIC_READ_ONLY;
  }
  return grant || GRANT_HIDDEN;
}

/**
 * @param {string | null | undefined} grant
 * @param {CapabilityAction} action
 * @returns {boolean}
 */
export function isGrantActionAllowed(grant, action) {
  const g = grant || GRANT_HIDDEN;
  if (g === GRANT_HIDDEN || g === GRANT_DENY) {
    return false;
  }
  if (g === GRANT_PLAN_GATED) {
    return false;
  }
  if (action === 'read') {
    return g === GRANT_ALLOW || g === GRANT_READ || g === GRANT_LIMITED;
  }
  if (action === 'write') {
    return g === GRANT_ALLOW || g === GRANT_LIMITED;
  }
  return false;
}

/**
 * @param {Record<string, string> | null | undefined} capabilities
 * @param {string} capabilityId
 * @param {CapabilityAction} action
 * @returns {{ allowed: boolean, grant: string, effectiveSemantic: string }}
 */
export function evaluateCapabilityGrant(capabilities, capabilityId, action) {
  const caps = capabilities || {};
  const grant = caps[capabilityId] || GRANT_HIDDEN;
  const effectiveSemantic = normalizeGrantSemantic(grant);
  return {
    allowed: isGrantActionAllowed(grant, action),
    grant,
    effectiveSemantic,
  };
}

/**
 * Parse governed lifecycle-aware API payload (403/401 detail object).
 * @param {unknown} detail
 * @returns {object | null}
 */
export function parseLifecycleResponseDetail(detail) {
  if (!detail || typeof detail !== 'object') {
    return null;
  }
  if (typeof detail.message !== 'string') {
    return null;
  }
  return detail;
}

/**
 * Parse governed capability_denied API payload (403 detail object).
 * @param {unknown} detail
 * @returns {object | null}
 */
export function parseCapabilityDeniedDetail(detail) {
  const parsed = parseLifecycleResponseDetail(detail);
  if (!parsed) {
    return null;
  }
  if (parsed.error !== CAPABILITY_DENIED_ERROR && parsed.response_type !== CAPABILITY_DENIED_ERROR) {
    return null;
  }
  return parsed;
}

/**
 * @param {unknown} detail
 * @returns {string | null}
 */
export function lifecycleRedirectRouteFromDetail(detail) {
  const redirect = detail?.lifecycle_redirect;
  if (redirect && typeof redirect.route === 'string' && redirect.route.trim()) {
    return redirect.route.trim();
  }
  const recovery = detail?.recovery;
  if (recovery && typeof recovery.route === 'string' && recovery.route.trim()) {
    return recovery.route.trim();
  }
  return null;
}

/**
 * @param {unknown} error Axios-like error or raw detail
 * @returns {object | null}
 */
export function extractCapabilityDeniedFromError(error) {
  if (!error) {
    return null;
  }
  if (typeof error === 'object' && error.error === CAPABILITY_DENIED_ERROR) {
    return error;
  }
  const responseDetail = error.response?.data?.detail;
  if (responseDetail) {
    return parseCapabilityDeniedDetail(responseDetail);
  }
  return parseCapabilityDeniedDetail(error.detail);
}

/**
 * @param {unknown} error
 * @returns {boolean}
 */
export function isCapabilityDeniedError(error) {
  return Boolean(extractCapabilityDeniedFromError(error));
}

/**
 * Coerce FastAPI `detail` (string, lifecycle object, or validation array) to display text.
 * @param {unknown} detail
 * @param {string} [fallback]
 * @returns {string}
 */
function coerceDisplayText(value) {
  if (value == null || value === '') {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}

function coerceCustomerExperienceCta(cta) {
  if (!cta || typeof cta !== 'object') {
    return null;
  }
  const label = coerceDisplayText(cta.label);
  const route = coerceDisplayText(cta.route);
  if (!label || !route) {
    return null;
  }
  return { label, route };
}

/**
 * Coerce Runtime Contract customer_experience fields for safe React rendering.
 * @param {unknown} cx
 * @returns {Record<string, unknown>}
 */
export function normalizeCustomerExperience(cx) {
  if (!cx || typeof cx !== 'object') {
    return {
      heading: '',
      explanation: '',
      reason: '',
      current_state_label: '',
      recovery_guidance: '',
      support_guidance: '',
      expected_next_step: '',
      primary_cta: null,
      secondary_cta: null,
    };
  }
  return {
    ...cx,
    heading: coerceDisplayText(cx.heading),
    explanation: coerceDisplayText(cx.explanation),
    reason: coerceDisplayText(cx.reason),
    current_state_label: coerceDisplayText(cx.current_state_label),
    recovery_guidance: coerceDisplayText(cx.recovery_guidance),
    support_guidance: coerceDisplayText(cx.support_guidance),
    expected_next_step: coerceDisplayText(cx.expected_next_step),
    primary_cta: coerceCustomerExperienceCta(cx.primary_cta),
    secondary_cta: coerceCustomerExperienceCta(cx.secondary_cta),
  };
}

export function coercePortalDisplayText(value, fallback = '') {
  return formatApiErrorDetail(value, fallback);
}

export function formatApiErrorDetail(detail, fallback = 'Something went wrong') {
  if (detail == null || detail === '') {
    return fallback;
  }
  if (typeof detail === 'string') {
    return sanitizeCapabilityCustomerMessage(detail, null, detail);
  }
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (first && typeof first.msg === 'string') {
      return first.msg;
    }
    return fallback;
  }
  if (typeof detail === 'object') {
    const portalMode = detail.portal_mode;
    const parsed = parseLifecycleResponseDetail(detail);
    if (parsed?.message) {
      return sanitizeCapabilityCustomerMessage(parsed.message, portalMode, parsed.message);
    }
    if (typeof detail.message === 'string') {
      return sanitizeCapabilityCustomerMessage(detail.message, portalMode, detail.message);
    }
    if (typeof detail.reason === 'string') {
      return sanitizeCapabilityCustomerMessage(detail.reason, portalMode, detail.reason);
    }
  }
  return fallback;
}

/**
 * @param {unknown} error Axios-like error
 * @param {string} [fallback]
 * @returns {string}
 */
export function formatApiErrorMessage(error, fallback = 'Something went wrong') {
  if (!error) {
    return fallback;
  }
  const denied = extractCapabilityDeniedFromError(error);
  if (denied?.message) {
    return sanitizeCapabilityCustomerMessage(
      denied.message,
      denied.portal_mode,
      denied.message,
    );
  }
  const detail = error.response?.data?.detail ?? error.detail;
  return formatApiErrorDetail(detail, fallback);
}
