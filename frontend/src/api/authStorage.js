/**
 * Canonical browser auth token storage — single source for portal JWT keys.
 * Pages must not read localStorage token keys directly; use these helpers or apiClient.
 */

export const AUTH_TOKEN_KEY = 'auth_token';
export const CONTRACTOR_TOKEN_KEY = 'contractor_token';
/** Legacy drift key — do not write; read only for migration warnings. */
export const LEGACY_TOKEN_KEY = 'token';

export function getAuthToken() {
  if (typeof window === 'undefined') return null;
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  return token && token.trim() ? token.trim() : null;
}

export function getContractorToken() {
  if (typeof window === 'undefined') return null;
  const token = localStorage.getItem(CONTRACTOR_TOKEN_KEY);
  return token && token.trim() ? token.trim() : null;
}

export function getPortalAuthToken(pathname = '') {
  if (typeof window !== 'undefined' && String(pathname || window.location.pathname || '').startsWith('/contractor')) {
    return getContractorToken();
  }
  return getAuthToken();
}

export function hasLegacyTokenDrift() {
  if (typeof window === 'undefined') return false;
  return Boolean(localStorage.getItem(LEGACY_TOKEN_KEY)) && !getAuthToken();
}
