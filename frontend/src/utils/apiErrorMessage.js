/**
 * Normalize FastAPI / axios error payloads for safe UI display (never render raw objects in JSX).
 */

export function formatApiDetail(detail, fallback = 'Request failed') {
  if (detail == null || detail === '') return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (d && typeof d === 'object' ? d.msg || JSON.stringify(d) : String(d))).join('; ');
  }
  if (typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) return detail.message;
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return String(detail);
}

export function apiErrorMessage(err, fallback = 'Request failed') {
  return formatApiDetail(err?.response?.data?.detail, err?.message || fallback);
}

/** Coerce arbitrary API field values to React-safe display text. */
export function formatDisplayValue(value, fallback = '—') {
  if (value == null || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    if (typeof value.message === 'string' && value.message.trim()) return value.message;
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }
  return String(value);
}
