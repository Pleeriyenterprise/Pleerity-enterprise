import axios from 'axios';

// Backend base URL: required in deployed env; fallback to relative /api for same-origin/proxy
const _raw = process.env.REACT_APP_BACKEND_URL;
const API_URL = typeof _raw === 'string' && _raw.trim() ? _raw.trim().replace(/\/$/, '') : '';

// Runtime debug: log backend URL once; expose for debug panel
if (typeof window !== 'undefined') {
  if (process.env.NODE_ENV !== 'production' || window.__CVP_DEBUG) {
    window.__CVP_BACKEND_URL = API_URL || '(not set - using relative /api)';
    console.debug('[CVP] REACT_APP_BACKEND_URL:', window.__CVP_BACKEND_URL);
    if (!API_URL) {
      console.warn('[CVP] REACT_APP_BACKEND_URL is not set; API calls use relative /api (ensure proxy or same host).');
    }
  }
}

// Track first 3 API requests for debug (URL + status)
let apiRequestCount = 0;
function logApiRequest(url, status, message) {
  if (apiRequestCount >= 3) return;
  apiRequestCount += 1;
  const statusStr = status != null ? String(status) : (message || 'no response');
  console.log(`[CVP] API request #${apiRequestCount}:`, url, '→', statusStr);
}

// Expose last API error for debug panel (?debug=1)
function setLastApiError(status, message) {
  if (typeof window !== 'undefined') {
    window.__CVP_LAST_API_ERROR = { status, message, at: new Date().toISOString() };
  }
}

const apiClient = axios.create({
  baseURL: API_URL ? `${API_URL}/api` : '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intake checkout debug: log URL, status, and structured detail (error_code, request_id) when present
function logIntakeDebug(method, fullUrl, status, data) {
  if (process.env.NODE_ENV === 'production' && !(typeof window !== 'undefined' && window.__CVP_DEBUG)) return;
  const detail = data?.detail;
  const payload = { method, url: fullUrl, status };
  if (detail && typeof detail === 'object') {
    if (detail.request_id) payload.request_id = detail.request_id;
    if (detail.error_code) payload.error_code = detail.error_code;
  }
  console.debug('[CVP] Intake', payload);
}

/** Relative path under /api (e.g. contractor/work-orders). */
function normalizedApiUrlPath(config) {
  return String(config.url || '').replace(/^\//, '');
}

/**
 * Contractor portal uses `contractor_token`; client portal uses `auth_token`.
 * If we always attached auth_token, contractor API calls would send the wrong JWT (403/401)
 * whenever a user still had a client session in the same browser.
 * Job-link routes use ?token= only — do not attach client Bearer.
 */
function applyPortalAuthHeader(config) {
  if (typeof window === 'undefined') return;
  const path = normalizedApiUrlPath(config);
  if (path.startsWith('contractor/')) {
    const ct = localStorage.getItem('contractor_token');
    if (ct) {
      config.headers.Authorization = `Bearer ${ct}`;
    } else {
      delete config.headers.Authorization;
    }
    return;
  }
  if (path.startsWith('job/')) {
    delete config.headers.Authorization;
    return;
  }
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  } else {
    delete config.headers.Authorization;
  }
}

// Request interceptor: add auth token + dev log first request (endpoint + Authorization)
let firstRequestLogged = false;
apiClient.interceptors.request.use(
  (config) => {
    applyPortalAuthHeader(config);
    // FormData must use multipart/form-data with boundary; do not send application/json
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    if (!firstRequestLogged && typeof window !== 'undefined' && (process.env.NODE_ENV !== 'production' || window.__CVP_DEBUG)) {
      firstRequestLogged = true;
      const url = config.url ?? config.baseURL ?? '?';
      const path = normalizedApiUrlPath(config);
      const mode = path.startsWith('contractor/')
        ? 'contractor_token'
        : path.startsWith('job/')
          ? 'job_token_query'
          : 'auth_token';
      console.log('[CVP] First API request:', url, 'authMode:', mode);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response: log first 3 requests, 401 → logout + redirect, 403 → track, track last error for debug panel
apiClient.interceptors.response.use(
  (response) => {
    const url = response.config?.url ?? response.config?.baseURL ?? '?';
    logApiRequest(url, response.status);
    const fullUrl = (response.config?.baseURL || '') + (response.config?.url || '');
    if (fullUrl.includes('/intake/submit') || fullUrl.includes('/intake/checkout')) {
      logIntakeDebug(response.config?.method?.toUpperCase() || 'GET', fullUrl, response.status, response.data);
    }
    return response;
  },
  (error) => {
    const url = error.config?.url ?? error.config?.baseURL ?? '?';
    const status = error.response?.status;
    const data = error.response?.data;
    const detail = data?.detail;
    const message = (typeof detail === 'string' ? detail : detail?.message) ?? error.message ?? 'Network error';
    logApiRequest(url, status, message);
    const fullUrl = (error.config?.baseURL || '') + (error.config?.url || '');
    if (fullUrl.includes('/intake/submit') || fullUrl.includes('/intake/checkout')) {
      logIntakeDebug(error.config?.method?.toUpperCase() || 'GET', fullUrl, status, data);
    }
    setLastApiError(status, typeof message === 'string' ? message : JSON.stringify(detail ?? message));
    const errPath = normalizedApiUrlPath(error.config || {});
    if (errPath.startsWith('contractor/') && typeof window !== 'undefined') {
      if (process.env.NODE_ENV !== 'production' || window.__CVP_CONTRACTOR_DEBUG) {
        console.warn('[CVP][Contractor] API error', {
          path: errPath,
          method: error.config?.method,
          status,
          detail: typeof detail === 'string' ? detail : detail?.message || message,
        });
      }
      try {
        sessionStorage.setItem(
          'cvp_contractor_last_api_error',
          JSON.stringify({
            path: errPath,
            status,
            at: new Date().toISOString(),
            detail: typeof detail === 'string' ? detail : detail?.message || String(message),
          })
        );
      } catch {
        /* ignore */
      }
    }
    // Plan-gate 403: attach so UI can show upgrade state instead of crashing
    if (status === 403 && data && (data.upgrade_required === true || data.feature || data.feature_key)) {
      error.isPlanGateDenied = true;
      error.upgradeDetail = typeof detail === 'object' ? detail : { message, feature: data.feature ?? data.feature_key, upgrade_required: true };
    }
    // Plan-restricted job/workflow creation (string 403s without upgrade_required JSON)
    const method = (error.config?.method || 'get').toLowerCase();
    if (status === 403 && method === 'post') {
      const rp = normalizedApiUrlPath(error.config || {});
      const detailStr =
        typeof detail === 'string'
          ? detail
          : detail && typeof detail.message === 'string'
            ? detail.message
            : '';

      const complianceJobPath =
        /^requirements\/[^/]+\/jobs$/.test(rp) ||
        rp === 'client/compliance-execution/work-orders/book' ||
        /^client\/maintenance\/risk-signals\/[^/]+\/(arrange-compliance-inspection|schedule-inspection)$/.test(rp);

      if (complianceJobPath) {
        const complianceBlocked =
          error.isPlanGateDenied === true ||
          /compliance jobs require\b/i.test(detailStr) ||
          (rp === 'client/compliance-execution/work-orders/book' &&
            /compliance engine is not enabled|work order workflows are not enabled/i.test(detailStr)) ||
          (/^client\/maintenance\/risk-signals\//.test(rp) &&
            /maintenance workflows are not enabled|predictive maintenance is not enabled/i.test(detailStr));
        if (complianceBlocked) {
          error.planRestrictedActionKind = 'compliance_job';
          if (/predictive maintenance is not enabled/i.test(detailStr)) {
            error.planRestrictedBillingFeatureKey = 'predictive_maintenance';
          }
        }
      }

      const maintenanceJobPath =
        rp === 'client/maintenance/work-orders' ||
        /^client\/maintenance\/issues\/[^/]+\/create-work-order$/.test(rp) ||
        /^client\/maintenance\/risk-signals\/[^/]+\/create-work-order$/.test(rp);

      if (maintenanceJobPath) {
        const maintenanceBlocked =
          error.isPlanGateDenied === true ||
          /maintenance workflows are not enabled/i.test(detailStr) ||
          /predictive maintenance is not enabled/i.test(detailStr);
        if (maintenanceBlocked) {
          error.planRestrictedActionKind = 'maintenance_job';
          if (/predictive maintenance is not enabled/i.test(detailStr) && !error.isPlanGateDenied) {
            error.planRestrictedBillingFeatureKey = 'predictive_maintenance';
          } else if (!error.isPlanGateDenied) {
            error.planRestrictedBillingFeatureKey = 'maintenance_workflows';
          }
        }
      }
    }
    // On 401: only redirect if this was NOT a login request (wrong credentials on login page should show error, not redirect)
    const requestUrl = error.config?.url || '';
    const isLoginRequest =
      requestUrl.includes('/auth/login') ||
      requestUrl.includes('/auth/admin/login') ||
      requestUrl.includes('/auth/contractor-login');
    if (status === 401 && !isLoginRequest) {
      const norm = requestUrl.replace(/^\//, '');
      // Contractor portal JWT is separate; do not clear client auth_token for contractor API failures.
      if (norm.startsWith('contractor/')) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('contractor_token');
          localStorage.removeItem('contractor_user');
          const path = window.location.pathname || '';
          if (path.startsWith('/contractor') && !path.includes('/login') && !path.includes('set-password')) {
            window.location.href = '/contractor/login?session_expired=1';
          }
        }
        return Promise.reject(error);
      }
      // Secure job link (no main session): never wipe client portal session on token expiry.
      if (norm.startsWith('job/')) {
        return Promise.reject(error);
      }
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user');
      const isAdminPath = typeof window !== 'undefined' && window.location.pathname.startsWith('/admin');
      window.location.href = isAdminPath ? '/login/admin?session_expired=1' : '/login?session_expired=1';
    }
    return Promise.reject(error);
  }
);

export { API_URL, setLastApiError };

/**
 * Map axios/FastAPI errors to a short, actionable message (retry / support / refresh where relevant).
 */
/** Short titles for job-link (`/api/job/*`) errors when `detail` includes `error_code`. */
const JOB_LINK_ERROR_TITLES = {
  JOB_TOKEN_EXPIRED: 'This link has expired',
  JOB_TOKEN_REVOKED: 'This link is no longer valid',
  JOB_TOKEN_INVALID: 'This link is not valid',
  JOB_TOKEN_MISSING: 'Invalid link',
  JOB_TOKEN_CONTRACTOR_MISSING: 'This link is no longer valid',
  CONTRACTOR_NOT_ACTIVE: 'Your account is not active',
  CONTRACTOR_PORTAL_DISABLED: 'Portal access is disabled',
  JOB_WORK_ORDER_NOT_FOUND: 'This job is no longer available',
  JOB_NOT_ASSIGNED_TO_YOU: 'This assignment has changed',
};

/**
 * Parse errors from secure job-link API calls into a clear title + message for full-page error UI.
 */
export function parseJobLinkError(
  err,
  fallbackMessage = 'We could not open this job. Contact the client if you need help.',
) {
  const message = parseApiError(err, fallbackMessage);
  const d = err?.response?.data?.detail;
  const code = d && typeof d === 'object' && d.error_code ? String(d.error_code) : null;
  const title =
    (code && JOB_LINK_ERROR_TITLES[code]) ||
    (err?.response?.status === 404 ? 'Cannot open this job' : null) ||
    (err?.response?.status === 401 ? 'This link cannot be used' : null) ||
    'Cannot open this job';
  return { title, message, errorCode: code };
}

export function parseApiError(err, fallback = 'Something went wrong. Please try again or refresh the page.') {
  if (!err || !err.response) {
    if (err && err.message === 'Network Error') {
      return 'Network error — check your connection and try again.';
    }
    return fallback;
  }
  const status = err.response.status;
  const d = err.response.data?.detail;
  if (typeof d === 'string' && d.trim()) return d.trim();
  if (d && typeof d === 'object') {
    if (typeof d.message === 'string' && d.message.trim()) {
      let msg = d.message.trim();
      if (d.retry_suggested === true) msg = `${msg} You can try again.`;
      return msg;
    }
    if (typeof d.error === 'string' && d.error.trim()) return d.error.trim();
  }
  if (status === 429) return 'Too many requests. Please wait a moment and try again.';
  if (status >= 500) return 'The service is temporarily unavailable. Please retry shortly or contact support.';
  return fallback;
}

export default apiClient;

/** Storage keys for files uploaded via contractor multipart evidence (path contains this segment). */
export function isContractorFileEvidenceKey(storageKey) {
  return typeof storageKey === 'string' && storageKey.includes('/contractor_evidence/') && !storageKey.startsWith('document:');
}

/** Best-effort display/download filename from an evidence key. */
export function contractorEvidenceFilenameFromKey(storageKey) {
  if (!storageKey || typeof storageKey !== 'string') return 'evidence';
  const k = storageKey.trim();
  if (k.startsWith('document:')) return 'linked-document';
  const last = k.replace(/\\/g, '/').split('/').pop();
  return last && last.length ? last : 'evidence';
}

/** Preview (new tab) or save blob from an API response with responseType: 'blob'. */
export function openBlobApiResponse(res, { download = false, fallbackFilename = 'download' } = {}) {
  if (typeof window === 'undefined') return;
  const ct = res.headers['content-type'] || 'application/octet-stream';
  const blob = res.data instanceof Blob ? res.data : new Blob([res.data], { type: ct });
  const objectUrl = URL.createObjectURL(blob);
  if (download) {
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = fallbackFilename;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
  } else {
    window.open(objectUrl, '_blank', 'noopener,noreferrer');
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 120000);
  }
}

// API methods
export const authAPI = {
  login: (data) => apiClient.post('/auth/login', data),
  adminLogin: (data) => apiClient.post('/auth/admin/login', data),
  contractorLogin: (data) => apiClient.post('/auth/contractor-login', data),
  contractorSetPassword: (data) => apiClient.post('/auth/contractor-set-password', data),
  setPassword: (data) => apiClient.post('/auth/set-password', data),
  forgotPassword: (data) => apiClient.post('/auth/forgot-password', data),
  stopImpersonation: () => apiClient.post('/auth/impersonation/stop'),
  extendSession: () => apiClient.post('/auth/session/extend'),
  verifyStepUp: (body) => apiClient.post('/auth/step-up/verify', body),
  idleSessionNotify: () => apiClient.post('/auth/session/idle-notify'),
};

/** Public (pre-auth) service agreement for intake checkout — same axios instance, no Bearer required. */
export const publicAgreementsAPI = {
  getCurrent: (templateCode) =>
    apiClient.get('/public/agreements/current', {
      params: templateCode ? { template_code: templateCode } : undefined,
    }),
  postAcceptance: (body) => apiClient.post('/public/agreements/acceptance', body),
};

export const intakeAPI = {
  /** Same duplicate rule as submit; rate-limited. Use before advancing past step 1. */
  checkEmailAvailability: (email) => apiClient.post('/intake/check-email', { email }),
  submit: (data) => apiClient.post('/intake/submit', data),
  previewRequirements: (properties) => apiClient.post('/intake/requirements-preview', { properties }),
  createCheckout: (clientId, body) => {
    const origin = window.location.origin;
    const cid = typeof clientId === 'string' ? clientId.trim() : '';
    const acceptance_id =
      body && typeof body.acceptance_id === 'string' ? body.acceptance_id.trim() : '';
    if (!cid) {
      return Promise.reject(
        Object.assign(new Error('checkout_missing_client_id'), {
          response: { status: 400, data: { detail: 'Missing client_id for checkout' } },
        }),
      );
    }
    if (!acceptance_id) {
      return Promise.reject(
        Object.assign(new Error('checkout_missing_acceptance_id'), {
          response: { status: 400, data: { detail: 'Missing agreement acceptance_id for checkout' } },
        }),
      );
    }
    return apiClient.post('/intake/checkout', { acceptance_id }, {
      params: { client_id: cid },
      headers: { origin },
    });
  },
  getOnboardingStatus: (clientId) => apiClient.get(`/intake/onboarding-status/${clientId}`),
  getPlans: () => apiClient.get('/intake/plans'),
  searchCouncils: (q, nation = null, page = 1, limit = 20) => 
    apiClient.get('/intake/councils', { params: { q, nation, page, limit } }),
  autocompletePostcode: (q) => apiClient.get('/intake/postcode-autocomplete', { params: { q } }),
  lookupPostcode: (postcode) => apiClient.get(`/intake/postcode-lookup/${encodeURIComponent(postcode)}`),
  uploadDocument: (formData) => apiClient.post('/intake/upload-document', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  validatePropertyCount: (planId, propertyCount) => 
    apiClient.post('/intake/validate-property-count', { plan_id: planId, property_count: propertyCount }),
  /** Prefill from risk-check: GET lead-from-token (signed token from Activate Monitoring email). */
  getLeadFromToken: (leadToken) =>
    apiClient.get('/risk-check/lead-from-token', { params: { lead_token: leadToken } })
};

export const clientAPI = {
  getDashboard: () => apiClient.get('/client/dashboard'),
  /** Month-to-date ROI-style metrics; fetch separately so main dashboard is not blocked. */
  getDashboardRoiSummary: () => apiClient.get('/client/dashboard/roi-summary'),
  /** Ranked priority actions (orchestration/copilot layer). */
  getPriorityActions: (params = {}) => apiClient.get('/client/priority-actions', { params }),
  /** Unified Command Centre tasks (sections, freshness, spend snapshot). */
  getTasks: (params = {}) => apiClient.get('/client/tasks', { params }),
  /** Same response as getTasks — stable alias for integrations and “Today / priorities” clients. */
  getPriorities: (params = {}) => apiClient.get('/client/priorities', { params }),
  /** Dashboard digest: summary, freshness, short activity (no full task lists). */
  getTasksDigest: (params = {}) => apiClient.get('/client/tasks/digest', { params }),
  /** Composed urgent tasks, risks, activity, compliance summary (read-only aggregate). */
  getCommandCenter: (params = {}) => apiClient.get('/client/command-center', { params }),
  /** Read-only security / continuity snapshot (account hints, compliance counts, issues, risk signals). */
  getProtectionSnapshot: (params = {}) => apiClient.get('/client/protection-snapshot', { params }),
  /** Phase 2: snooze | dismiss | done | restore (inbox overlay). */
  postTaskOverride: (body) => apiClient.post('/client/tasks/override', body),
  /** Audited navigation intent from Today (before SPA route change). */
  recordTaskNavigationIntent: (body) => apiClient.post('/client/tasks/record-intent', body),
  /** Start a COMPLIANCE work order directly from tenant request. */
  startTenantRequestComplianceJob: (requestId, body = {}) =>
    apiClient.post(`/client/tenant-requests/${encodeURIComponent(requestId)}/start-compliance-job`, body),
  getTasksActivity: (params = {}) => apiClient.get('/client/tasks/activity', { params }),
  /** Deltas since last acknowledged dashboard visit (cursor advanced via acknowledgeActivitySince). */
  getActivitySince: () => apiClient.get('/client/activity-since'),
  acknowledgeActivitySince: () => apiClient.post('/client/activity-since/acknowledge', {}),
  /** First-party analytics (allowed event names enforced server-side). */
  postAnalyticsEvent: (body) => apiClient.post('/client/analytics/events', body),
  /** Aggregated event counts by name for this tenant (query: days 7–90). */
  getAnalyticsSummary: (params = {}) => apiClient.get('/client/analytics/summary', { params }),
  /** Compliance evidence ZIP (CSVs + manifest); requires audit_log_export. Max 5 / 24h. */
  createEvidencePackJob: (body = {}) => apiClient.post('/client/evidence-pack/jobs', body),
  getEntitlementsContext: () => apiClient.get('/client/entitlements/context'),
  listEvidencePackJobs: (params = {}) => apiClient.get('/client/evidence-pack/jobs', { params }),
  downloadEvidencePackFile: (jobId) =>
    apiClient.get(`/client/evidence-pack/jobs/${encodeURIComponent(jobId)}/file`, { responseType: 'blob' }),
  /** Open maintenance issues count (non-terminal statuses). Requires MAINTENANCE_WORKFLOWS. */
  getOpenIssuesCount: () => apiClient.get('/client/maintenance/issues/open-count'),
  /** Paid invoice total this UTC month (maintenance/contractor). Requires INVOICING. */
  getMaintenanceSpendThisMonth: () => apiClient.get('/client/finance/maintenance-spend-this-month'),
  getEntitlements: () => apiClient.get('/client/entitlements'),
  getProperties: () => apiClient.get('/client/properties'),
  /** PATCH /api/properties/{id} — partial property update (e.g. jurisdiction). */
  patchProperty: (propertyId, body) => apiClient.patch(`/properties/${encodeURIComponent(propertyId)}`, body),
  /** Writes account default onto properties that have no explicit jurisdiction (mixed portfolios safe). */
  applyDefaultJurisdictionToMissingProperties: () =>
    apiClient.post('/client/settings/jurisdiction/apply-to-missing-properties', {}),
  getPropertyRequirements: (propertyId) => apiClient.get(`/client/properties/${propertyId}/requirements`),
  getRequirementExplanation: (propertyId, params) => apiClient.get(`/client/properties/${propertyId}/requirements/explanation`, { params: params || {} }),
  /** Mark a catalog requirement as not applicable for this property (creates/updates requirement row). */
  markRequirementNotApplicable: (propertyId, body) =>
    apiClient.post(`/client/properties/${propertyId}/requirements/mark-not-applicable`, body),
  getRequirements: () => apiClient.get('/client/requirements'),
  /** List documents. Optional params: { property_id, requirement_id } to filter. */
  getDocuments: (params) => apiClient.get('/documents', { params: params || {} }),
  /** Audit Intelligence: portfolio score, risk_level, properties summary */
  getComplianceSummary: () => apiClient.get('/portfolio/compliance-summary'),
  /** Property compliance detail: matrix, property_score, risk_index, risk_level (catalog-driven when available). */
  getComplianceDetail: (propertyId) =>
    apiClient.get(`/portfolio/properties/${propertyId}/compliance-detail`),
  /** Score change history for property (score_change_log entries). */
  getScoreHistory: (propertyId, limit = 20) =>
    apiClient.get(`/portfolio/properties/${propertyId}/score-history`, { params: { limit } }),
  /** Action -> Outcome timeline (score/risk/status impact per action). */
  getComplianceActivity: (params = {}) => apiClient.get('/client/compliance/activity', { params }),
  /** Property-level compliance score explainability (v2 buckets + requirements + deficits/actions). */
  getPropertyComplianceScoreExplanation: (propertyId) =>
    apiClient.get(`/client/properties/${propertyId}/compliance-score/explanation`),
  /** Unified property timeline (ledger + score log + work orders). */
  getPropertyTimeline: (propertyId, params = {}) =>
    apiClient.get(`/portfolio/properties/${propertyId}/timeline`, { params }),
  /** Evidence vault for property: summary, documents, recentEvents (Evidence tab). */
  getPropertyEvidence: (propertyId) =>
    apiClient.get(`/portfolio/properties/${propertyId}/evidence`),
  /** Generate Evidence Readiness PDF (POST body: { scope: 'portfolio' | 'property', property_id? }). Returns blob. */
  generateEvidenceReadinessReport: (body) =>
    apiClient.post('/reports/generate', body, { responseType: 'blob' }),
  /** List previous Evidence Readiness report runs (metadata). */
  listEvidenceReadinessReports: () => apiClient.get('/reports'),
  /** Download a previous report by id (re-generates PDF). Returns blob. */
  downloadEvidenceReadinessReport: (reportId) =>
    apiClient.get(`/reports/${reportId}/download`, { responseType: 'blob' }),
  /** Client-scoped audit timeline (read-only). */
  getAuditTimeline: (limit = 50) =>
    apiClient.get('/portfolio/audit-timeline', { params: { limit } }),
  /** Score ledger: paginated list of score change events. */
  getLedger: (params = {}) =>
    apiClient.get('/client/ledger', { params: { limit: 50, ...params } }),
  /** Export score ledger as CSV (blob). */
  exportLedgerCsv: (params = {}) =>
    apiClient.get('/client/ledger/export.csv', { params, responseType: 'blob' }),
  /** Server-driven onboarding checklist (items + completion). */
  getOnboardingChecklist: () => apiClient.get('/client/onboarding/checklist'),
  /** Mark a checklist item complete (server-validates). */
  completeOnboardingItem: (itemId) =>
    apiClient.post(`/client/onboarding/checklist/items/${encodeURIComponent(itemId)}/complete`),
  /** Explicit acknowledgement to continue onboarding while some properties lack jurisdiction on record. */
  acknowledgeJurisdictionFallbackAssumptions: (body) =>
    apiClient.post('/client/onboarding/jurisdiction-fallback-acknowledgement', body),
  /** Achievements, at-risk counts, plan unlock copy (billing-backed entitlements). */
  getValueInsights: () => apiClient.get('/client/value-insights'),
  /** Jurisdiction settings (default + enabled list). */
  getJurisdictionSettings: () => apiClient.get('/client/settings/jurisdiction'),
  updateJurisdictionSettings: (body) => apiClient.patch('/client/settings/jurisdiction', body),
  /** Maintenance work orders (requires MAINTENANCE_WORKFLOWS). */
  getMaintenanceWorkOrders: (params = {}) => apiClient.get('/client/maintenance/work-orders', { params }),
  getMaintenanceWorkOrder: (workOrderId) => apiClient.get(`/client/maintenance/work-orders/${workOrderId}`),
  getMaintenanceWorkOrderContractorEvidenceFile: (workOrderId, storageKey, download = false) =>
    apiClient.get(`/client/maintenance/work-orders/${workOrderId}/contractor-evidence/file`, {
      params: { storage_key: storageKey, ...(download ? { download: true } : {}) },
      responseType: 'blob',
    }),
  createMaintenanceWorkOrder: (body) => apiClient.post('/client/maintenance/work-orders', body),
  updateMaintenanceWorkOrder: (workOrderId, body) => apiClient.patch(`/client/maintenance/work-orders/${workOrderId}`, body),
  proposeMaintenanceSchedule: (workOrderId, body) =>
    apiClient.post(`/client/maintenance/work-orders/${workOrderId}/schedule/propose`, body),
  confirmMaintenanceSchedule: (workOrderId) =>
    apiClient.post(`/client/maintenance/work-orders/${workOrderId}/schedule/confirm`, {}),
  requestMaintenanceScheduleReschedule: (workOrderId, body) =>
    apiClient.post(`/client/maintenance/work-orders/${workOrderId}/schedule/reschedule-request`, body),
  cancelMaintenanceSchedule: (workOrderId) =>
    apiClient.post(`/client/maintenance/work-orders/${workOrderId}/schedule/cancel`, {}),
  getMaintenanceScheduleIcs: (workOrderId) =>
    apiClient.get(`/client/maintenance/work-orders/${workOrderId}/schedule/ics`, { responseType: 'blob' }),
  getRecommendContractors: (workOrderId, params = {}) => apiClient.get(`/client/maintenance/work-orders/${workOrderId}/recommend-contractors`, { params }),
  /** Maintenance issues (create issue → triage → create work order). */
  getMaintenanceIssues: (params = {}) => apiClient.get('/client/maintenance/issues', { params }),
  getMaintenanceIssue: (issueId) => apiClient.get(`/client/maintenance/issues/${issueId}`),
  /** Read-only issue timeline (newest first). */
  getMaintenanceIssueTimeline: (issueId, params = {}) =>
    apiClient.get(`/client/maintenance/issues/${issueId}/timeline`, { params }),
  createMaintenanceIssue: (body) => apiClient.post('/client/maintenance/issues', body),
  createWorkOrderFromIssue: (issueId) => apiClient.post(`/client/maintenance/issues/${issueId}/create-work-order`),
  updateMaintenanceIssue: (issueId, body) => apiClient.patch(`/client/maintenance/issues/${issueId}`, body),
  /** Predictive maintenance insights (requires PREDICTIVE_MAINTENANCE). */
  getPredictiveInsights: (params = {}) => apiClient.get('/client/maintenance/predictive-insights', { params }),
  /** Property assets for predictive (requires MAINTENANCE_WORKFLOWS or PREDICTIVE_MAINTENANCE). */
  getPropertyAssets: (propertyId) => apiClient.get(`/client/maintenance/properties/${propertyId}/assets`),
  ensureDefaultAssetsForProperty: (propertyId) => apiClient.post(`/client/maintenance/properties/${propertyId}/assets/ensure-defaults`),
  getPropertyAsset: (propertyId, assetId) => apiClient.get(`/client/maintenance/properties/${propertyId}/assets/${assetId}`),
  addPropertyAsset: (propertyId, body) => apiClient.post(`/client/maintenance/properties/${propertyId}/assets`, body),
  updatePropertyAsset: (propertyId, assetId, body) => apiClient.patch(`/client/maintenance/properties/${propertyId}/assets/${assetId}`, body),
  getPropertyAssetEvents: (propertyId, assetId, params = {}) => apiClient.get(`/client/maintenance/properties/${propertyId}/assets/${assetId}/events`, { params }),
  /** Maintenance events for predictive (requires PREDICTIVE_MAINTENANCE). */
  getPropertyEvents: (propertyId, params = {}) => apiClient.get(`/client/maintenance/properties/${propertyId}/events`, { params }),
  addPropertyEvent: (propertyId, body) => apiClient.post(`/client/maintenance/properties/${propertyId}/events`, body),
  /** Risk signals (stored, rule-based). Requires PREDICTIVE_MAINTENANCE. */
  getPropertyRiskSignals: (propertyId, params = {}) => apiClient.get(`/client/maintenance/properties/${propertyId}/risk-signals`, { params }),
  getRiskSignals: (params = {}) => apiClient.get('/client/maintenance/risk-signals', { params }),
  getRiskSignal: (signalId) => apiClient.get(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}`),
  getRiskSignalExplanation: (signalId) => apiClient.get(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/explanation`),
  getRiskSignalSuggestedActions: (signalId) =>
    apiClient.get(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/suggested-actions`),
  createIssueFromRiskSignal: (signalId, body = {}) => apiClient.post(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/create-issue`, body),
  createWorkOrderFromRiskSignal: (signalId, body = {}) => apiClient.post(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/create-work-order`, body),
  /** Canonical: creates a COMPLIANCE work order (requires obligation fields in body). */
  arrangeComplianceInspectionFromRiskSignal: (signalId, body) =>
    apiClient.post(
      `/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/arrange-compliance-inspection`,
      body,
    ),
  /** Maintenance-only: inspection-flavoured issue, not a compliance job. */
  logInspectionIssueFromRiskSignal: (signalId, body = {}) =>
    apiClient.post(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/log-inspection-issue`, body),
  /** @deprecated Use arrangeComplianceInspectionFromRiskSignal (same server behaviour as arrange-compliance-inspection). */
  scheduleInspectionFromRiskSignal: (signalId, body) =>
    apiClient.post(
      `/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/arrange-compliance-inspection`,
      body,
    ),
  recalculatePropertyRiskSignals: (propertyId) => apiClient.post(`/client/maintenance/risk-signals/recalculate/${propertyId}`),
  updateRiskSignalStatus: (signalId, status, dismissReason = null) =>
    apiClient.patch(`/client/maintenance/risk-signals/${signalId}`, {
      status,
      ...(dismissReason ? { dismiss_reason: dismissReason } : {}),
    }),
  /** Dismiss a risk signal (resolved) with mandatory reason when no execution closure exists server-side. */
  dismissRiskSignal: (signalId, dismissReason) =>
    apiClient.patch(`/client/maintenance/risk-signals/${signalId}`, { status: 'resolved', dismiss_reason: dismissReason }),
  getMaintenanceContractorRoutingState: (workOrderId) =>
    apiClient.get(`/client/maintenance/work-orders/${workOrderId}/contractor-routing`),
  requestMaintenanceContractor: (workOrderId) =>
    apiClient.post(`/client/maintenance/work-orders/${workOrderId}/contractor-routing/request`),
  confirmMaintenanceContractorRecommendation: (workOrderId) =>
    apiClient.post(`/client/maintenance/work-orders/${workOrderId}/contractor-routing/confirm`),
  /** Compliance execution jobs (COMPLIANCE work orders). Requires COMPLIANCE_ENGINE + MAINTENANCE_WORKFLOWS. */
  bookComplianceWorkOrder: (body) => apiClient.post('/client/compliance-execution/work-orders/book', body),
  /** Top-level /api compliance workflow surface (requirements, jobs, Today). */
  getRequirementWorkflow: (requirementId) => apiClient.get(`/requirements/${encodeURIComponent(requirementId)}`),
  createRequirementComplianceJob: (requirementId, body = {}) =>
    apiClient.post(`/requirements/${encodeURIComponent(requirementId)}/jobs`, body),
  markRequirementNotApplicableById: (requirementId, body) =>
    apiClient.post(`/requirements/${encodeURIComponent(requirementId)}/mark-not-applicable`, body),
  reopenRequirementById: (requirementId) => apiClient.post(`/requirements/${encodeURIComponent(requirementId)}/reopen`, {}),
  getComplianceWorkflowJob: (jobId) => apiClient.get(`/jobs/${encodeURIComponent(jobId)}`),
  postJobDecisionLog: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/decision-log`, body),
  getJobAssignableContractors: (jobId, params = {}) =>
    apiClient.get(`/jobs/${encodeURIComponent(jobId)}/assignable-contractors`, { params }),
  createWorkflowContractor: (body) => apiClient.post('/contractors', body),
  complianceJobAssignContractor: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/assign-contractor`, body),
  complianceJobRequestBooking: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/request-booking`, body),
  complianceJobReschedule: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/reschedule`, body),
  complianceJobCancelBooking: (jobId) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/cancel-booking`, {}),
  complianceJobMarkNoAccess: (jobId, body = {}) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/mark-no-access`, body),
  complianceJobMarkRescheduleRequired: (jobId) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/mark-reschedule-required`, {}),
  complianceJobConfirmBooking: (jobId) => apiClient.post(`/jobs/${encodeURIComponent(jobId)}/confirm-booking`, {}),
  complianceJobStart: (jobId) => apiClient.post(`/jobs/${encodeURIComponent(jobId)}/start`, {}),
  complianceJobAwaitingParts: (jobId) => apiClient.post(`/jobs/${encodeURIComponent(jobId)}/awaiting-parts`, {}),
  complianceJobComplete: (jobId) => apiClient.post(`/jobs/${encodeURIComponent(jobId)}/complete`, {}),
  complianceJobLinkDocument: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/link-document`, body),
  complianceJobAttachCompletionProof: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/attach-completion-proof`, body),
  complianceJobClose: (jobId) => apiClient.post(`/jobs/${encodeURIComponent(jobId)}/close`, {}),
  complianceJobVerify: (jobId) => apiClient.post(`/jobs/${encodeURIComponent(jobId)}/verify`, {}),
  complianceJobCancel: (jobId) => apiClient.post(`/jobs/${encodeURIComponent(jobId)}/cancel`, {}),
  getTodayItems: (params = {}) => apiClient.get('/today/items', { params }),
  todayItemMarkReviewed: (itemId) => apiClient.post(`/today/items/${encodeURIComponent(itemId)}/mark-reviewed`, {}),
  todayItemSnooze: (itemId, days) => apiClient.post(`/today/items/${encodeURIComponent(itemId)}/snooze`, { days }),
  todayItemDismiss: (itemId, reason) =>
    apiClient.post(`/today/items/${encodeURIComponent(itemId)}/dismiss`, { reason }),
  todayItemRestore: (itemId) => apiClient.post(`/today/items/${encodeURIComponent(itemId)}/restore`, {}),
  complianceJobSetOperationalException: (jobId, exception) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/operational-exception`, { exception: exception || '' }),
  complianceJobResumeAfterParts: (jobId) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/resume-after-parts`, {}),
  complianceJobSubmitQuote: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/submit-quote`, body),
  complianceJobApproveQuote: (jobId) => apiClient.post(`/jobs/${encodeURIComponent(jobId)}/approve-quote`, {}),
  complianceJobRejectQuote: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/reject-quote`, body ?? {}),
  complianceJobMarkInspectionComplete: (jobId) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/mark-inspection-complete`, {}),
  complianceJobCreatePersonalContractorAndAssign: (jobId, body) =>
    apiClient.post(`/jobs/${encodeURIComponent(jobId)}/create-personal-contractor-and-assign`, body),
  requestDocumentValidation: (documentId) => apiClient.post(`/documents/${encodeURIComponent(documentId)}/validate`, {}),
  getComplianceContractorRoutingState: (workOrderId) =>
    apiClient.get(`/client/compliance-execution/work-orders/${workOrderId}/contractor-routing`),
  requestComplianceContractor: (workOrderId) =>
    apiClient.post(`/client/compliance-execution/work-orders/${workOrderId}/contractor-routing/request`),
  confirmComplianceContractorRecommendation: (workOrderId) =>
    apiClient.post(`/client/compliance-execution/work-orders/${workOrderId}/contractor-routing/confirm`),
  /** Contractors available to client (requires CONTRACTOR_NETWORK). */
  getContractors: (params = {}) => apiClient.get('/client/contractors', { params }),
  getContractorExplanation: (contractorId) => apiClient.get(`/client/contractors/${encodeURIComponent(contractorId)}/explanation`),
  /** Submit private contractor for network review (requires CONTRACTOR_NETWORK). */
  submitContractorToNetwork: (contractorId) => apiClient.post(`/client/contractors/${contractorId}/submit-to-network`),
  /** Landlord-add contractor (requires CONTRACTOR_NETWORK). */
  createContractor: (body) => apiClient.post('/client/contractors', body),
  /** Rate a contractor (e.g. after work order). */
  rateContractor: (contractorId, body) => apiClient.post(`/client/contractors/${contractorId}/rate`, body),
  /** Approvals (invoice/work order). Requires INVOICING. */
  getApprovals: (params = {}) => apiClient.get('/client/approvals', { params }),
  getApproval: (invoiceId) => apiClient.get(`/client/approvals/${encodeURIComponent(invoiceId)}`),
  updateApproval: (invoiceId, body, config = {}) =>
    apiClient.patch(`/client/approvals/${encodeURIComponent(invoiceId)}`, body, config),
  createInvoice: (body) => apiClient.post('/client/invoices', body),
  exportApprovals: (params = {}) => apiClient.get('/client/approvals/export', { params, responseType: 'blob' }),
  /** In-app notifications (portal user). */
  getInAppNotifications: (params = {}) => apiClient.get('/profile/in-app-notifications', { params }),
  getInAppNotificationsUnreadCount: () => apiClient.get('/profile/in-app-notifications/unread-count'),
  markInAppNotificationRead: (notificationId) =>
    apiClient.patch(`/profile/in-app-notifications/${encodeURIComponent(notificationId)}/read`),
  markAllInAppNotificationsRead: () => apiClient.post('/profile/in-app-notifications/read-all'),
  dismissInAppNotification: (notificationId) =>
    apiClient.post(`/profile/in-app-notifications/${encodeURIComponent(notificationId)}/dismiss`),
  recordInAppNotificationCta: (notificationId, body = { action_key: 'primary' }) =>
    apiClient.post(`/profile/in-app-notifications/${encodeURIComponent(notificationId)}/cta`, body),
  /** Server time + last audit activity (trust / freshness for portal shell). */
  getPortalContext: () => apiClient.get('/client/portal-context'),
  /** Active system banners (auth only; visible before full provisioning). */
  getActiveSystemBanners: () => apiClient.get('/profile/system-banners/active'),
  dismissSystemBanner: (bannerId) => apiClient.post(`/profile/system-banners/${encodeURIComponent(bannerId)}/dismiss`),
};

export const adminAPI = {
  getDashboard: () => apiClient.get('/admin/dashboard'),
  globalSearch: (q, limit = 20, includeArchived = false) =>
    apiClient.get('/admin/search', { params: { q, limit, include_archived: includeArchived || undefined } }),
  getPendingVerificationDocuments: (hours = 0, clientId = null, limit = 50, skip = 0) =>
    apiClient.get('/admin/documents/pending-verification', { params: { hours, client_id: clientId || undefined, limit, skip } }),
  getClients: (skip = 0, limit = 50) => apiClient.get('/admin/clients', { params: { skip, limit } }),
  getClientDetail: (clientId) => apiClient.get(`/admin/clients/${clientId}`),
  /** Pending payments / intake list buckets: pending | archived | purge_eligible | test_like | all */
  getPendingPayments: (params = {}) => apiClient.get('/admin/intake/pending-payments', { params }),
  archiveClient: (clientId, body, config = {}) =>
    apiClient.post(`/admin/clients/${clientId}/archive`, body ?? {}, config),
  restoreClient: (clientId, config = {}) => apiClient.post(`/admin/clients/${clientId}/restore`, null, config),
  markClientPurgeEligible: (clientId, config = {}) =>
    apiClient.post(`/admin/clients/${clientId}/mark-purge-eligible`, null, config),
  flagClientTestLike: (clientId, body, config = {}) =>
    apiClient.post(`/admin/clients/${clientId}/flag-test-like`, body ?? {}, config),
  getClientPermanentDeleteCheck: (clientId) => apiClient.get(`/admin/clients/${clientId}/permanent-delete-check`),
  permanentDeleteClient: (clientId, config = {}) => apiClient.delete(`/admin/clients/${clientId}/permanent`, config),
  /** Unified identity lifecycle (clients, contractors, portal users). */
  listIdentities: (params = {}) => apiClient.get('/admin/identities', { params }),
  identityArchive: (kind, id, body = {}, config = {}) =>
    apiClient.post(
      `/admin/identities/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/archive`,
      body,
      config,
    ),
  identityRestore: (kind, id, config = {}) =>
    apiClient.post(`/admin/identities/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/restore`, {}, config),
  identitySuspend: (kind, id, config = {}) =>
    apiClient.post(`/admin/identities/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/suspend`, {}, config),
  identityResume: (kind, id, config = {}) =>
    apiClient.post(`/admin/identities/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/resume`, {}, config),
  identityMarkPurgeEligible: (kind, id, config = {}) =>
    apiClient.post(`/admin/identities/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/mark-purge-eligible`, {}, config),
  identityPermanentDeleteCheck: (kind, id) =>
    apiClient.get(`/admin/identities/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/permanent-delete-check`),
  identityPermanentDelete: (kind, id, config = {}) =>
    apiClient.delete(`/admin/identities/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/permanent`, config),
  identitySetTestLike: (kind, id, body, config = {}) =>
    apiClient.post(
      `/admin/identities/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/test-like`,
      body,
      config,
    ),
  portalUserSetTestLike: (portalUserId, body, config = {}) =>
    apiClient.post(`/admin/users/${encodeURIComponent(portalUserId)}/test-like`, body, config),
  retryProvisioningJob: (jobId) => apiClient.post(`/admin/provisioning-jobs/${jobId}/retry`),
  getClientControlPanel: (clientId) => apiClient.get(`/admin/clients/${clientId}/control-panel`),
  getClientComplianceActivity: (clientId, params = {}) =>
    apiClient.get(`/admin/clients/${clientId}/compliance-activity`, { params }),
  getClientCommandCentreTaskActivity: (clientId, params = {}) =>
    apiClient.get(`/admin/clients/${clientId}/command-centre-task-activity`, { params }),
  resendActivationEmail: (clientId) => apiClient.post(`/admin/clients/${clientId}/actions/resend-activation-email`),
  resendDashboardEmail: (clientId) => apiClient.post(`/admin/clients/${clientId}/actions/resend-dashboard-email`),
  recalculateCompliance: (clientId) => apiClient.post(`/admin/clients/${clientId}/actions/recalculate-compliance`),
  runClientJob: (clientId, job = 'compliance_recalc_client') => apiClient.post(`/admin/clients/${clientId}/actions/run-job`, { job }),
  unlockClientAccount: (clientId) => apiClient.post(`/admin/clients/${clientId}/actions/unlock-account`),
  startClientImpersonation: (clientId, ttlMinutes = 30) =>
    apiClient.post(`/admin/clients/${clientId}/impersonation/start`, null, { params: { ttl_minutes: ttlMinutes } }),
  getClientReceipts: (clientId, params = {}) => apiClient.get(`/admin/billing/clients/${clientId}/receipts`, { params }),
  resendClientReceipt: (clientId, body) => apiClient.post(`/admin/billing/clients/${clientId}/receipts/resend`, body),
  getAuditLogs: (params = {}) =>
    apiClient.get('/admin/audit-logs', {
      params: {
        skip: params.skip ?? 0,
        limit: params.limit ?? 100,
        ...(params.client_id ? { client_id: params.client_id } : {}),
        ...(params.action ? { action: params.action } : {}),
        ...(params.start_date ? { start_date: params.start_date } : {}),
        ...(params.end_date ? { end_date: params.end_date } : {}),
      },
    }),
  getComplianceClientsSummary: (params = {}) =>
    apiClient.get('/admin/ops/compliance-clients-summary', { params }),
  /** Requirement external action links — preview / draft / publish / revert (Owner/Admin). */
  getPropertyRequirementsLite: (propertyId) =>
    apiClient.get(`/admin/properties/${encodeURIComponent(propertyId)}/requirements-lite`),
  getRequirementActionLinksPreview: (propertyId, requirementId) =>
    apiClient.get(
      `/admin/properties/${encodeURIComponent(propertyId)}/requirements/${encodeURIComponent(requirementId)}/action-links`,
    ),
  putRequirementActionLinksDraft: (propertyId, requirementId, body) =>
    apiClient.put(
      `/admin/properties/${encodeURIComponent(propertyId)}/requirements/${encodeURIComponent(requirementId)}/action-links/draft`,
      body,
    ),
  publishRequirementActionLinks: (propertyId, requirementId) =>
    apiClient.post(
      `/admin/properties/${encodeURIComponent(propertyId)}/requirements/${encodeURIComponent(requirementId)}/action-links/publish`,
    ),
  revertRequirementActionLinks: (propertyId, requirementId) =>
    apiClient.post(
      `/admin/properties/${encodeURIComponent(propertyId)}/requirements/${encodeURIComponent(requirementId)}/action-links/revert`,
    ),
  /** Compliance requirement registry (Mongo drafts; engine compare only). */
  listComplianceRegistryDrafts: (params = {}) => apiClient.get('/admin/compliance/registry/drafts', { params }),
  getComplianceRegistryDraft: (entryId) =>
    apiClient.get(`/admin/compliance/registry/drafts/${encodeURIComponent(entryId)}`),
  createComplianceRegistryDraft: (body) => apiClient.post('/admin/compliance/registry/drafts', body),
  patchComplianceRegistryDraft: (entryId, body) =>
    apiClient.patch(`/admin/compliance/registry/drafts/${encodeURIComponent(entryId)}`, body),
  getComplianceRegistryDraftCompare: (entryId) =>
    apiClient.get(`/admin/compliance/registry/drafts/${encodeURIComponent(entryId)}/compare`),
  importComplianceRegistryBaselineBundle: (body = {}) =>
    apiClient.post('/admin/compliance/registry/import-baseline-bundle', body),
  getComplianceRegistryBaselineBundleMeta: () => apiClient.get('/admin/compliance/registry/baseline-bundle-meta'),
  getComplianceRegistryControlledFieldOptions: () =>
    apiClient.get('/admin/compliance/registry/controlled-field-options'),
  getComplianceRegistryPublishedEntryKeys: () => apiClient.get('/admin/compliance/registry/published/entry-keys'),
  getComplianceRegistryPublishImpact: (entryIdsCsv) =>
    apiClient.get('/admin/compliance/registry/publish-impact', { params: { entry_ids: entryIdsCsv } }),
  /** Same planner as production + read-only draft overlay merge (no writes). */
  getComplianceRegistryPreviewSimulation: (params) =>
    apiClient.get('/admin/compliance/registry/preview-simulation', { params }),
  listComplianceRegistryPublishQueue: () => apiClient.get('/admin/compliance/registry/publish-queue'),
  createComplianceRegistryPublishQueue: (body) => apiClient.post('/admin/compliance/registry/publish-queue', body),
  getComplianceRegistryPublishQueue: (queueId) =>
    apiClient.get(`/admin/compliance/registry/publish-queue/${encodeURIComponent(queueId)}`),
  submitComplianceRegistryPublishQueue: (queueId) =>
    apiClient.post(`/admin/compliance/registry/publish-queue/${encodeURIComponent(queueId)}/submit`),
  approveComplianceRegistryPublishQueue: (queueId) =>
    apiClient.post(`/admin/compliance/registry/publish-queue/${encodeURIComponent(queueId)}/approve`),
  rejectComplianceRegistryPublishQueue: (queueId, body) =>
    apiClient.post(`/admin/compliance/registry/publish-queue/${encodeURIComponent(queueId)}/reject`, body),
  publishComplianceRegistryPublishQueue: (queueId) =>
    apiClient.post(`/admin/compliance/registry/publish-queue/${encodeURIComponent(queueId)}/publish`),
  getComplianceRegistryPublishedActive: () => apiClient.get('/admin/compliance/registry/published/active'),
  listComplianceRegistryPublishedHistory: (params = {}) =>
    apiClient.get('/admin/compliance/registry/published/history', { params }),
  getComplianceRegistryPublishedHistoryVersion: (publishedLineVersion, params = {}) =>
    apiClient.get(
      `/admin/compliance/registry/published/history/${encodeURIComponent(String(publishedLineVersion))}`,
      { params },
    ),
  revertComplianceRegistryPublishedToVersion: (publishedLineVersion) =>
    apiClient.post(`/admin/compliance/registry/published/revert-to/${encodeURIComponent(String(publishedLineVersion))}`),
  /** Per-property: re-materialise requirements from catalog + active published registry (Owner/Admin/Support). */
  syncPropertyRequirementsFromRegistry: (propertyId) =>
    apiClient.post(`/admin/properties/${encodeURIComponent(propertyId)}/requirements/sync-from-registry`),
  getEmailDelivery: (params = {}) =>
    apiClient.get('/admin/email-delivery', { params: { limit: 50, skip: 0, since_hours: 72, ...params } }),
  resendPasswordSetup: (clientId, config = {}) =>
    apiClient.post(`/admin/clients/${clientId}/resend-password-setup`, null, config),
  /** GET password setup link. generateNew=true revokes old tokens and requires step-up on the server. */
  getPasswordSetupLink: (clientId, generateNew = false, config = {}) =>
    apiClient.get(`/admin/clients/${clientId}/password-setup-link`, {
      ...config,
      params: { generate_new: generateNew, ...(config.params || {}) },
    }),
  // Admin user management
  listAdmins: () => apiClient.get('/admin/admins'),
  inviteAdmin: (data) => apiClient.post('/admin/admins/invite', data),
  deactivateAdmin: (portalUserId) => apiClient.delete(`/admin/admins/${portalUserId}`),
  reactivateAdmin: (portalUserId) => apiClient.post(`/admin/admins/${portalUserId}/reactivate`),
  resendAdminInvite: (portalUserId) => apiClient.post(`/admin/admins/${portalUserId}/resend-invite`),
  getComplianceScoreHistory: (propertyId, limit = 20) =>
    apiClient.get(`/admin/properties/${propertyId}/compliance-score-history`, { params: { limit } }),
  // Observability (job runs, incidents, system health)
  getObservabilityHealthSummary: () => apiClient.get('/admin/observability/health-summary'),
  getAutomationFrameworkAudit: () => apiClient.get('/admin/observability/framework-audit'),
  getJobRuns: (params = {}) => apiClient.get('/admin/observability/job-runs', { params }),
  getJobRunMessageLogs: (runId, params = {}) =>
    apiClient.get(`/admin/observability/job-runs/${runId}/message-logs`, { params }),
  getJobRunMessageLogsCsv: (runId, limit = 2000) =>
    apiClient.get(`/admin/observability/job-runs/${runId}/message-logs`, {
      params: { format: 'csv', limit },
      responseType: 'blob',
    }),
  getDeliveryStateDefinitions: () => apiClient.get('/admin/observability/delivery-state-definitions'),
  getIncidents: (params = {}) => apiClient.get('/admin/observability/incidents', { params }),
  getIncident: (incidentId) => apiClient.get(`/admin/observability/incidents/${incidentId}`),
  acknowledgeIncident: (incidentId, note) =>
    apiClient.post(`/admin/observability/incidents/${incidentId}/ack`, note != null ? { note } : {}),
  resolveIncident: (incidentId, note) =>
    apiClient.post(`/admin/observability/incidents/${incidentId}/resolve`, note != null ? { note } : {}),
  getScoreEvents: (params = {}) => apiClient.get('/admin/observability/score-events', { params }),
  // Security monitoring and incident detection
  getSecurityDashboard: (params = {}) => apiClient.get('/admin/security/dashboard', { params }),
  getSecurityEvents: (params = {}) => apiClient.get('/admin/security/events', { params }),
  getSecurityIncidents: (params = {}) => apiClient.get('/admin/security/incidents', { params }),
  resolveSecurityIncident: (incidentKey, note) =>
    apiClient.post(`/admin/security/incidents/${encodeURIComponent(incidentKey)}/resolve`, note != null ? { note } : {}),
  /** Unified Control Centre (health, automation, security, revenue, engagement, alerts). */
  getControlCentreSnapshot: () => apiClient.get('/admin/control-centre/snapshot'),
  /** Run a background job; pass a string job id or { job, client_id?, property_id? } for scoped runs (e.g. monthly_digest + client_id). */
  runJobNow: (jobOrBody) =>
    typeof jobOrBody === 'string'
      ? apiClient.post('/admin/jobs/run', { job: jobOrBody })
      : apiClient.post('/admin/jobs/run', jobOrBody),
  // Operations & Compliance
  getOpsOverview: () => apiClient.get('/admin/ops/overview'),
  /** Admin priority actions (action queue / operational priorities). */
  getPriorityActions: (params = {}) => apiClient.get('/admin/ops/priority-actions', { params }),
  getClientFeatureFlags: (clientId) => apiClient.get(`/admin/ops/clients/${clientId}/feature-flags`),
  updateClientFeatureFlags: (clientId, updates) =>
    apiClient.patch(`/admin/ops/clients/${clientId}/feature-flags`, { updates }),
  getClientPlanUsage: (clientId) => apiClient.get(`/admin/ops/clients/${clientId}/plan-usage`),
  /** Read-only ROI month summary + diagnostics (same as client card; ops debugging). */
  getClientDashboardRoiDiagnostics: (clientId) =>
    apiClient.get(`/admin/ops/clients/${encodeURIComponent(clientId)}/dashboard-roi-diagnostics`),
  // Contractors (Ops Contractor Network)
  getContractors: (params = {}) => apiClient.get('/admin/ops/contractors', { params }),
  getContractorAnalytics: (params = {}) => apiClient.get('/admin/ops/contractors/analytics', { params }),
  getContractor: (contractorId) => apiClient.get(`/admin/ops/contractors/${contractorId}`),
  getContractorExplanation: (contractorId) => apiClient.get(`/admin/ops/contractors/${encodeURIComponent(contractorId)}/explanation`),
  createContractor: (body) => apiClient.post('/admin/ops/contractors', body),
  createNetworkContractor: (body) => apiClient.post('/admin/ops/contractors/network', body),
  approveContractor: (contractorId) => apiClient.patch(`/admin/ops/contractors/${contractorId}/approve`),
  approveContractorToNetwork: (contractorId) =>
    apiClient.patch(`/admin/ops/contractors/${contractorId}/approve-to-network`),
  rejectContractorNetworkSubmission: (contractorId, body) =>
    apiClient.patch(`/admin/ops/contractors/${contractorId}/reject-network-submission`, body || {}),
  updateContractor: (contractorId, body) => apiClient.patch(`/admin/ops/contractors/${contractorId}`, body),
  deleteContractor: (contractorId) => apiClient.delete(`/admin/ops/contractors/${contractorId}`),
  resendContractorPortalInvite: (contractorId) => apiClient.post(`/admin/ops/contractors/${contractorId}/invite-portal/resend`),
  disableContractorPortalAccess: (contractorId, body = {}) =>
    apiClient.post(`/admin/ops/contractors/${contractorId}/portal-access/disable`, body),
  getContractorAssignedJobs: (contractorId, params = {}) =>
    apiClient.get(`/admin/ops/contractors/${contractorId}/assigned-jobs`, { params }),
  // Work orders (Ops Maintenance)
  getWorkOrders: (params = {}) => apiClient.get('/admin/ops/work-orders', { params }),
  getWorkOrder: (workOrderId) => apiClient.get(`/admin/ops/work-orders/${workOrderId}`),
  getWorkOrderContractorEvidenceFile: (workOrderId, storageKey, download = false) =>
    apiClient.get(`/admin/ops/work-orders/${workOrderId}/contractor-evidence/file`, {
      params: { storage_key: storageKey, ...(download ? { download: true } : {}) },
      responseType: 'blob',
    }),
  getRecommendContractors: (workOrderId, params = {}) => apiClient.get(`/admin/ops/work-orders/${workOrderId}/recommend-contractors`, { params }),
  createWorkOrder: (body) => apiClient.post('/admin/ops/work-orders', body),
  updateWorkOrder: (workOrderId, body) => apiClient.patch(`/admin/ops/work-orders/${workOrderId}`, body),
  // Predictive insights (admin: per client; client: own)
  getClientPredictiveInsights: (clientId, params = {}) => apiClient.get(`/admin/ops/clients/${clientId}/predictive-insights`, { params }),
  // Risk signals (admin dashboard)
  getRiskSignalsSummary: (params = {}) => apiClient.get('/admin/ops/risk-signals/summary', { params }),
  // Invoices (admin create)
  createInvoice: (body) => apiClient.post('/admin/ops/invoices', body),
  // Contractor portal invite (admin)
  inviteContractorToPortal: (contractorId) => apiClient.post(`/admin/ops/contractors/${contractorId}/invite-portal`),
  inviteContractor: (body) => apiClient.post('/admin/ops/contractors/invite', body),
  // Admin communications (Owner/Admin for send/templates/banners; all admin roles can read history)
  communicationsPreview: (body) => apiClient.post('/admin/communications/preview', body),
  communicationsSend: (body) => apiClient.post('/admin/communications/send', body),
  communicationsDraftUpsert: (body) => apiClient.post('/admin/communications/drafts', body),
  communicationsDrafts: () => apiClient.get('/admin/communications/drafts'),
  communicationsDraftDelete: (communicationId) =>
    apiClient.delete(`/admin/communications/drafts/${encodeURIComponent(communicationId)}`),
  communicationsSchedule: (body) => apiClient.post('/admin/communications/schedule', body),
  communicationsMessages: (params = {}) => apiClient.get('/admin/communications/messages', { params }),
  communicationsMessage: (communicationId) => apiClient.get(`/admin/communications/messages/${encodeURIComponent(communicationId)}`),
  communicationsResendDeliveryEmail: (deliveryId) =>
    apiClient.post(`/admin/communications/deliveries/${encodeURIComponent(deliveryId)}/resend-email`),
  communicationsTemplates: () => apiClient.get('/admin/communications/templates'),
  communicationsTemplateCreate: (body) => apiClient.post('/admin/communications/templates', body),
  communicationsTemplateUpdate: (templateId, body) =>
    apiClient.put(`/admin/communications/templates/${encodeURIComponent(templateId)}`, body),
  communicationsBanners: (params = {}) => apiClient.get('/admin/communications/banners', { params }),
  communicationsBannerCreate: (body) => apiClient.post('/admin/communications/banners', body),
  communicationsBannerPatch: (bannerId, body) =>
    apiClient.patch(`/admin/communications/banners/${encodeURIComponent(bannerId)}`, body),
  /** In-app notification inbox (admin bell). */
  getInAppNotifications: (params = {}) => apiClient.get('/admin/notifications', { params }),
  getInAppNotificationsUnreadCount: () => apiClient.get('/admin/notifications/unread-count'),
  markInAppNotificationRead: (notificationId) =>
    apiClient.post(`/admin/notifications/${encodeURIComponent(notificationId)}/read`),
  markAllInAppNotificationsRead: () => apiClient.post('/admin/notifications/read-all'),
  dismissInAppNotification: (notificationId) =>
    apiClient.post(`/admin/notifications/${encodeURIComponent(notificationId)}/dismiss`),
  recordInAppNotificationCta: (notificationId, body = { action_key: 'primary' }) =>
    apiClient.post(`/admin/notifications/${encodeURIComponent(notificationId)}/cta`, body),
};

// Contractor portal API (use with contractor token from contractor login/set-password)
export function createContractorAPI(accessToken) {
  const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
  return {
    getWorkOrders: (params = {}) => apiClient.get('/contractor/work-orders', { params, headers }),
    getWorkOrder: (id) => apiClient.get(`/contractor/work-orders/${id}`, { headers }),
    updateWorkOrder: (id, body) => apiClient.patch(`/contractor/work-orders/${id}`, body, { headers }),
    acceptAssignment: (id) => apiClient.post(`/contractor/work-orders/${id}/accept`, {}, { headers }),
    declineAssignment: (id) => apiClient.post(`/contractor/work-orders/${id}/decline`, {}, { headers }),
    submitInvoice: (body) => apiClient.post('/contractor/invoices', body, { headers }),
    resubmitInvoice: (invoiceId, body) =>
      apiClient.patch(`/contractor/invoices/${encodeURIComponent(invoiceId)}/resubmit`, body, { headers }),
    getProfile: () => apiClient.get('/contractor/profile', { headers }),
    getDashboardSummary: () => apiClient.get('/contractor/dashboard-summary', { headers }),
    getInvoices: (params = {}) => apiClient.get('/contractor/invoices', { params, headers }),
    uploadWorkOrderEvidence: (workOrderId, file) => {
      const fd = new FormData();
      fd.append('file', file);
      return apiClient.post(`/contractor/work-orders/${workOrderId}/evidence`, fd, { headers });
    },
    downloadWorkOrderEvidenceFile: (workOrderId, storageKey, download = false) =>
      apiClient.get(`/contractor/work-orders/${workOrderId}/evidence/file`, {
        params: { storage_key: storageKey, ...(download ? { download: true } : {}) },
        headers,
        responseType: 'blob',
      }),
    proposeSchedule: (workOrderId, body) =>
      apiClient.post(`/contractor/work-orders/${workOrderId}/schedule/propose`, body, { headers }),
    confirmSchedule: (workOrderId) =>
      apiClient.post(`/contractor/work-orders/${workOrderId}/schedule/confirm`, {}, { headers }),
    requestScheduleReschedule: (workOrderId, body) =>
      apiClient.post(`/contractor/work-orders/${workOrderId}/schedule/reschedule-request`, body, { headers }),
    cancelSchedule: (workOrderId) =>
      apiClient.post(`/contractor/work-orders/${workOrderId}/schedule/cancel`, {}, { headers }),
    markNoAccess: (workOrderId, body = {}) =>
      apiClient.post(`/contractor/work-orders/${workOrderId}/mark-no-access`, body, { headers }),
    getScheduleIcs: (workOrderId) =>
      apiClient.get(`/contractor/work-orders/${workOrderId}/schedule/ics`, { headers, responseType: 'blob' }),
    postWorkflowUsage: (body) => apiClient.post('/contractor/workflow-usage', body, { headers }),
    submitJobQuote: (workOrderId, body) =>
      apiClient.post(`/jobs/${encodeURIComponent(workOrderId)}/submit-quote`, body, { headers }),
    markJobInspectionComplete: (workOrderId) =>
      apiClient.post(`/jobs/${encodeURIComponent(workOrderId)}/mark-inspection-complete`, {}, { headers }),
  };
}

// Job link API (no login: use token from secure link in assignment email)
export function createJobLinkAPI(jobToken) {
  const params = jobToken ? { token: jobToken } : {};
  const config = (opts = {}) => ({ ...opts, params: { ...params, ...(opts.params || {}) } });
  return {
    getWorkOrder: () => apiClient.get('/job/work-order', config()),
    updateWorkOrder: (body) => apiClient.patch('/job/work-order', body, config()),
    acceptAssignment: () => apiClient.post('/job/work-order/accept', {}, config()),
    declineAssignment: () => apiClient.post('/job/work-order/decline', {}, config()),
    submitInvoice: (body) => apiClient.post('/job/invoices', body, config()),
    uploadWorkOrderEvidence: (file) => {
      const fd = new FormData();
      fd.append('file', file);
      return apiClient.post('/job/work-order/evidence', fd, config());
    },
    downloadWorkOrderEvidenceFile: (storageKey, download = false) =>
      apiClient.get('/job/work-order/evidence/file', {
        ...config({
          params: { storage_key: storageKey, ...(download ? { download: true } : {}) },
        }),
        responseType: 'blob',
      }),
    proposeSchedule: (body) => apiClient.post('/job/work-order/schedule/propose', body, config()),
    confirmSchedule: () => apiClient.post('/job/work-order/schedule/confirm', {}, config()),
    requestScheduleReschedule: (body) => apiClient.post('/job/work-order/schedule/reschedule-request', body, config()),
    cancelSchedule: () => apiClient.post('/job/work-order/schedule/cancel', {}, config()),
    markNoAccess: (body = {}) => apiClient.post('/job/work-order/mark-no-access', body, config()),
    getScheduleIcs: () => apiClient.get('/job/work-order/schedule/ics', { ...config(), responseType: 'blob' }),
    postWorkflowUsage: (body) => apiClient.post('/job/workflow-usage', body, config()),
    submitQuote: (body) => apiClient.post('/job/submit-quote', body, config()),
    markInspectionComplete: () => apiClient.post('/job/mark-inspection-complete', {}, config()),
  };
}
