/**
 * UK full postcode checks aligned with backend `agreement_render_context._looks_like_uk_postcode`
 * (compact form: optional single inward group = digit + two letters).
 */

const UK_POSTCODE_COMPACT_RE = /^[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}$/i;

/**
 * True when value is a complete UK postcode (not outward-only, not truncated).
 * @param {string | null | undefined} value
 * @returns {boolean}
 */
export function isFullUkPostcode(value) {
  const compact = String(value || '')
    .trim()
    .replace(/\s+/g, '')
    .toUpperCase();
  if (compact.length < 5 || compact.length > 8) return false;
  return UK_POSTCODE_COMPACT_RE.test(compact);
}

/**
 * Normalise spacing for display/storage — mirrors `agreement_commercial_snapshot._normalize_uk_postcode`.
 * @param {string | null | undefined} value
 * @returns {string}
 */
export function normalizeUkPostcode(value) {
  let s = String(value || '').trim().toUpperCase();
  if (!s) return '';
  s = s.split(/\s+/).join(' ');
  const nospace = s.replace(/\s/g, '');
  if (nospace.length > 3 && !s.includes(' ')) {
    s = `${nospace.slice(0, -3)} ${nospace.slice(-3)}`;
  }
  return s;
}

/** Strip characters that should never appear in a UK postcode field (commas, etc.). */
export function sanitizePostcodeFieldInput(value) {
  return String(value || '')
    .toUpperCase()
    .replace(/[^A-Z0-9\s]/g, '');
}
