/**
 * Intake email helpers — mirror backend `utils.client_email.canonical_client_email`
 * (trim + ASCII lowercase) for stale-response checks and display consistency.
 */

export const INTAKE_EMAIL_DEBOUNCE_MS = 500;

/** Same copy as backend `INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE` (intake submit + duplicate-key). */
export const INTAKE_EMAIL_DUPLICATE_MESSAGE = 'An account with this email already exists';

export function canonicalIntakeEmail(email) {
  if (email == null) return '';
  return String(email).trim().toLowerCase();
}

/** Basic format gate before calling POST /api/intake/check-email (matches wizard step-1 validation). */
export function isIntakeEmailFormatValid(raw) {
  const t = String(raw ?? '').trim();
  if (!t) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t);
}
