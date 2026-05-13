/**
 * L-009 client presentation — read-only display of optional API `propagation_notice`.
 * Does not alter authority, scoring, or queue behaviour; surfaces backend `message` when present.
 *
 * Stable codes mirror `backend/services/client_propagation_notice.py` (display only).
 */
export const PROPAGATION_NOTICE_CODE_AUTHORITY_DEFERRED = 'COMPLIANCE_PROPAGATION_DEFERRED_AUTHORITY_SYNC';
export const PROPAGATION_NOTICE_CODE_RECALC_DEFERRED = 'COMPLIANCE_PROPAGATION_DEFERRED_SCORE_RECALC';

const HEADLINE = 'Update still applying';

/**
 * @param {unknown} raw — `{ code?, message? }` from API or null/undefined
 * @returns {{ headline: string, body: string, code: string|null }|null}
 */
export function propagationNoticeForUi(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const code = typeof raw.code === 'string' && raw.code.trim() ? raw.code.trim() : null;
  const message = typeof raw.message === 'string' && raw.message.trim() ? raw.message.trim() : null;
  if (!code && !message) return null;
  return {
    headline: HEADLINE,
    body: message || fallbackBodyForCode(code),
    code,
  };
}

function fallbackBodyForCode(code) {
  if (code === PROPAGATION_NOTICE_CODE_AUTHORITY_DEFERRED) {
    return 'Linked evidence views may refresh once platform processing catches up. This is expected when compliance processing is temporarily limited.';
  }
  if (code === PROPAGATION_NOTICE_CODE_RECALC_DEFERRED) {
    return 'Your compliance score may refresh later when a background recalculation runs.';
  }
  return 'Some compliance updates are finishing in the background. Refresh this page in a moment if counts look unchanged.';
}
