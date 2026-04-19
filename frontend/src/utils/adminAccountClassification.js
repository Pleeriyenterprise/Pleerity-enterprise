/**
 * Single source for admin UI copy: non-production is determined only by `is_test_like`
 * on clients and portal_users (Mongo). No separate dummy/pre-production enum yet.
 */

export const NON_PRODUCTION_BADGE_TEXT = 'TEST / DUMMY / PRE-PRODUCTION';

export const PRODUCTION_ACCOUNT_LABEL = 'Production account';

export const NON_PRODUCTION_ACCOUNT_LABEL = 'Test / Dummy / Pre-production account';

/** @param {{ is_test_like?: boolean } | null | undefined} doc */
export function isNonProductionAccount(doc) {
  return Boolean(doc?.is_test_like);
}

/** One-line for confirm modals / toasts (must match list/detail badges). */
export function accountEnvironmentActionNote(isNonProduction) {
  if (isNonProduction) {
    return `Account class: ${NON_PRODUCTION_ACCOUNT_LABEL}. Permanent delete may apply only where policy allows (e.g. portal row after checks).`;
  }
  return `Account class: ${PRODUCTION_ACCOUNT_LABEL}. Use archive or deactivate — not casual permanent delete.`;
}

/** Client org: portal hard-delete is separate; keep wording honest. */
export function clientOrgPermanentDeleteHint(isNonProduction) {
  if (isNonProduction) {
    return 'Organisation flagged as non-production (is_test_like). Eligible for stronger cleanup workflows where your policy allows; client permanent delete still follows billing/data checks.';
  }
  return 'Live organisation — permanent client deletion follows strict checks; prefer archive / suspend for access control.';
}
