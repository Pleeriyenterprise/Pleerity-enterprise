/**
 * Client portal auth redirects: after setup, session expiry, or 401, send users to
 * `/login/client` with an optional internal `next` path — not the generic `/login` role chooser.
 */

const CLIENT_PATH_PREFIXES = [
  '/app',
  '/dashboard',
  '/today',
  '/tasks',
  '/properties',
  '/requirements',
  '/documents',
  '/calendar',
  '/reports',
  '/settings',
  '/assistant',
  '/help',
  '/compliance-score',
  '/tenant',
  '/tenants',
  '/integrations',
  '/orders',
  '/operations',
  '/command-center',
];

/**
 * True when pathname is a CVP client (or tenant) portal route protected by ClientPortal + JWT.
 */
export function isClientPortalPath(pathname) {
  if (!pathname || typeof pathname !== 'string') return false;
  return CLIENT_PATH_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

const NEXT_PATH_DISALLOWED_PREFIXES = ['/admin', '/login', '/clearform', '/contractor', '/job'];

/**
 * Allow only same-origin relative paths for `next` (open-redirect safe).
 * Returns normalized path + query or null.
 */
export function sanitizeClientLoginNextPath(raw) {
  if (raw == null || typeof raw !== 'string') return null;
  let s = raw.trim();
  if (!s) return null;
  try {
    s = decodeURIComponent(s);
  } catch {
    return null;
  }
  if (!s.startsWith('/') || s.startsWith('//')) return null;
  if (s.includes('://')) return null;
  if (s.length > 2048) return null;
  const pathOnly = s.split('?')[0];
  if (NEXT_PATH_DISALLOWED_PREFIXES.some((p) => pathOnly === p || pathOnly.startsWith(`${p}/`))) {
    return null;
  }
  return s;
}

export function buildClientLoginUrlWithNext(nextPath, extraParams = {}) {
  const safe = sanitizeClientLoginNextPath(nextPath);
  const qs = new URLSearchParams();
  Object.entries(extraParams).forEach(([k, v]) => {
    if (v != null && v !== '') qs.set(k, String(v));
  });
  if (safe) qs.set('next', safe);
  const q = qs.toString();
  return q ? `/login/client?${q}` : '/login/client';
}

/** After session expiry / 401 on a client portal page, return to the same URL after sign-in when safe. */
export function buildClientLoginSessionExpiredUrl(pathname, search = '') {
  const path = `${pathname || ''}${search || ''}`;
  if (!isClientPortalPath(pathname || '')) {
    return '/login/client?session_expired=1';
  }
  return buildClientLoginUrlWithNext(path, { session_expired: '1' });
}
