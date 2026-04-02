/**
 * Safe in-app paths for the client portal (React Router navigate / Link `to`).
 * Rejects hash-only links, external URLs, and paths with broken ID segments.
 */

function pathPartHasBadIdSegment(pathOnly) {
  if (!pathOnly) return true;
  return pathOnly.includes('/undefined') || /\/null(\/|$)/.test(pathOnly);
}

export function isSafeClientPortalPath(raw) {
  const s = raw == null ? '' : String(raw).trim();
  if (!s || s === '#' || s.startsWith('#')) return false;
  if (!s.startsWith('/') || s.startsWith('//')) return false;
  const pathOnly = s.split(/[?#]/)[0];
  return !pathPartHasBadIdSegment(pathOnly);
}

/**
 * @param {string|null|undefined} raw
 * @param {string} fallback
 */
export function resolveClientPortalPath(raw, fallback = '/today') {
  return isSafeClientPortalPath(raw) ? String(raw).trim() : fallback;
}

/** Normalizes IDs used in client-portal routes (property, issue, work order, etc.). */
export function normalizeRouteId(id) {
  if (id == null) return null;
  const s = String(id).trim();
  if (!s || s === 'undefined' || s === 'null') return null;
  return s;
}

/**
 * @param {string} basePath e.g. '/operations/work-orders'
 * @param {Record<string, string|number|undefined|null>} query
 */
export function buildSafeQueryPath(basePath, query = {}) {
  const q = new URLSearchParams();
  Object.entries(query).forEach(([k, v]) => {
    if (v == null || v === '') return;
    q.set(k, String(v));
  });
  const qs = q.toString();
  const full = `${basePath}${qs ? `?${qs}` : ''}`;
  return resolveClientPortalPath(full, basePath);
}

export function resolvePropertyPath(propertyId, suffix = '') {
  const id = normalizeRouteId(propertyId);
  if (!id) return '/properties';
  const suf =
    !suffix || suffix === ''
      ? ''
      : suffix.startsWith('?') || suffix.startsWith('#')
        ? suffix
        : `?${suffix}`;
  return resolveClientPortalPath(`/properties/${id}${suf}`, '/properties');
}

export function resolveDocumentsPath(propertyId, extraQuery = {}) {
  const id = normalizeRouteId(propertyId);
  if (!id) return '/documents';
  const q = new URLSearchParams();
  q.set('property_id', id);
  Object.entries(extraQuery).forEach(([k, v]) => {
    if (v == null || v === '') return;
    q.set(k, String(v));
  });
  return resolveClientPortalPath(`/documents?${q.toString()}`, '/documents');
}

/**
 * Build a strict entity-scoped client route for corrective actions.
 * For fix/review/upload/resolve actions, call this instead of inline strings.
 */
export function buildEntityRoute(
  { requirement_id, property_id, work_order_id, mode = 'upload' } = {},
  fallback = '/today'
) {
  const rid = normalizeRouteId(requirement_id);
  const pid = normalizeRouteId(property_id);
  const wid = normalizeRouteId(work_order_id);

  if (wid) {
    return buildSafeQueryPath('/operations/work-orders', { work_order_id: wid });
  }
  if (rid && pid) {
    if (mode === 'requirement' || mode === 'review') {
      return buildSafeQueryPath('/requirements', { highlight: rid, property_id: pid });
    }
    return buildSafeQueryPath('/documents', { property_id: pid, requirement_id: rid });
  }
  if (rid) {
    return buildSafeQueryPath('/requirements', { highlight: rid });
  }
  if (pid) {
    return buildSafeQueryPath('/requirements', { property_id: pid });
  }
  if (fallback === '') return '';
  return resolveClientPortalPath(fallback, '/today');
}

export function resolveIssueDetailPath(issueId) {
  const id = normalizeRouteId(issueId);
  if (!id) return '/operations/issues';
  return resolveClientPortalPath(`/operations/issues/${id}`, '/operations/issues');
}

export function resolveTenantPropertyPath(propertyId) {
  const id = normalizeRouteId(propertyId);
  if (!id) return '/tenant';
  return resolveClientPortalPath(`/tenant/properties/${id}`, '/tenant');
}

/**
 * Priority action from API: use recommended_url when safe; else related_property_id; else fallback.
 * @param {object|null|undefined} action
 * @param {string} [fallback='/today']
 */
export function resolvePriorityActionNavigateTarget(action, fallback = '/today') {
  const raw = action?.recommended_url;
  if (isSafeClientPortalPath(raw)) return String(raw).trim();
  const pidStr = normalizeRouteId(action?.related_property_id);
  if (pidStr) {
    return `/properties/${pidStr}`;
  }
  return fallback;
}

/** For diagnostics (ErrorBoundary); never log secrets. */
export function recordClientPortalInteraction(label, details = {}) {
  if (typeof window === 'undefined' || !window.sessionStorage) return;
  try {
    window.sessionStorage.setItem(
      'cvp_last_interaction',
      JSON.stringify({
        label: String(label || ''),
        path: `${window.location.pathname}${window.location.search}`,
        ...details,
        ts: new Date().toISOString(),
      })
    );
  } catch {
    /* ignore quota / private mode */
  }
}
