import axios from 'axios';

// Backend base URL: required in deployed env; fallback to relative /api for same-origin/proxy
const _raw = process.env.REACT_APP_BACKEND_URL;
const API_URL = typeof _raw === 'string' && _raw.trim() ? _raw.trim().replace(/\/$/, '') : '';

// Runtime debug: log backend URL once; expose for debug panel
if (typeof window !== 'undefined') {
  window.__CVP_BACKEND_URL = API_URL || '(not set - using relative /api)';
  if (process.env.NODE_ENV !== 'production' || window.__CVP_DEBUG) {
    console.debug('[CVP] REACT_APP_BACKEND_URL:', window.__CVP_BACKEND_URL);
  }
  if (!API_URL) {
    console.warn('[CVP] REACT_APP_BACKEND_URL is not set; API calls use relative /api (ensure proxy or same host).');
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

// Request interceptor: add auth token + dev log first request (endpoint + Authorization)
let firstRequestLogged = false;
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // FormData must use multipart/form-data with boundary; do not send application/json
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    if (!firstRequestLogged && typeof window !== 'undefined') {
      firstRequestLogged = true;
      const url = config.url ?? config.baseURL ?? '?';
      console.log('[CVP] First API request:', url, 'Authorization:', token ? 'Bearer present' : 'MISSING');
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
    // Plan-gate 403: attach so UI can show upgrade state instead of crashing
    if (status === 403 && data && (data.upgrade_required === true || data.feature || data.feature_key)) {
      error.isPlanGateDenied = true;
      error.upgradeDetail = typeof detail === 'object' ? detail : { message, feature: data.feature ?? data.feature_key, upgrade_required: true };
    }
    // On 401: only redirect if this was NOT a login request (wrong credentials on login page should show error, not redirect)
    const isLoginRequest = (error.config?.url || '').includes('/auth/login') || (error.config?.url || '').includes('/auth/admin/login');
    if (status === 401 && !isLoginRequest) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user');
      const isAdminPath = typeof window !== 'undefined' && window.location.pathname.startsWith('/admin');
      window.location.href = isAdminPath ? '/login/admin?session_expired=1' : '/login?session_expired=1';
    }
    return Promise.reject(error);
  }
);

export { API_URL, setLastApiError };

export default apiClient;

// API methods
export const authAPI = {
  login: (data) => apiClient.post('/auth/login', data),
  adminLogin: (data) => apiClient.post('/auth/admin/login', data),
  contractorLogin: (data) => apiClient.post('/auth/contractor-login', data),
  contractorSetPassword: (data) => apiClient.post('/auth/contractor-set-password', data),
  setPassword: (data) => apiClient.post('/auth/set-password', data),
  forgotPassword: (data) => apiClient.post('/auth/forgot-password', data),
  stopImpersonation: () => apiClient.post('/auth/impersonation/stop'),
};

export const intakeAPI = {
  submit: (data) => apiClient.post('/intake/submit', data),
  createCheckout: (clientId) => {
    const origin = window.location.origin;
    return apiClient.post('/intake/checkout', null, {
      params: { client_id: clientId },
      headers: { origin }
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
  /** Ranked priority actions (orchestration/copilot layer). */
  getPriorityActions: (params = {}) => apiClient.get('/client/priority-actions', { params }),
  getEntitlements: () => apiClient.get('/client/entitlements'),
  getProperties: () => apiClient.get('/client/properties'),
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
  /** Jurisdiction settings (default + enabled list). */
  getJurisdictionSettings: () => apiClient.get('/client/settings/jurisdiction'),
  updateJurisdictionSettings: (body) => apiClient.patch('/client/settings/jurisdiction', body),
  /** Maintenance work orders (requires MAINTENANCE_WORKFLOWS). */
  getMaintenanceWorkOrders: (params = {}) => apiClient.get('/client/maintenance/work-orders', { params }),
  getMaintenanceWorkOrder: (workOrderId) => apiClient.get(`/client/maintenance/work-orders/${workOrderId}`),
  createMaintenanceWorkOrder: (body) => apiClient.post('/client/maintenance/work-orders', body),
  updateMaintenanceWorkOrder: (workOrderId, body) => apiClient.patch(`/client/maintenance/work-orders/${workOrderId}`, body),
  getRecommendContractors: (workOrderId, params = {}) => apiClient.get(`/client/maintenance/work-orders/${workOrderId}/recommend-contractors`, { params }),
  /** Maintenance issues (create issue → triage → create work order). */
  getMaintenanceIssues: (params = {}) => apiClient.get('/client/maintenance/issues', { params }),
  getMaintenanceIssue: (issueId) => apiClient.get(`/client/maintenance/issues/${issueId}`),
  createMaintenanceIssue: (body) => apiClient.post('/client/maintenance/issues', body),
  createWorkOrderFromIssue: (issueId) => apiClient.post(`/client/maintenance/issues/${issueId}/create-work-order`),
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
  createIssueFromRiskSignal: (signalId, body = {}) => apiClient.post(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/create-issue`, body),
  createWorkOrderFromRiskSignal: (signalId, body = {}) => apiClient.post(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/create-work-order`, body),
  scheduleInspectionFromRiskSignal: (signalId, body = {}) => apiClient.post(`/client/maintenance/risk-signals/${encodeURIComponent(signalId)}/schedule-inspection`, body),
  recalculatePropertyRiskSignals: (propertyId) => apiClient.post(`/client/maintenance/risk-signals/recalculate/${propertyId}`),
  updateRiskSignalStatus: (signalId, status) => apiClient.patch(`/client/maintenance/risk-signals/${signalId}`, { status }),
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
  updateApproval: (invoiceId, body) => apiClient.patch(`/client/approvals/${encodeURIComponent(invoiceId)}`, body),
  createInvoice: (body) => apiClient.post('/client/invoices', body),
  exportApprovals: (params = {}) => apiClient.get('/client/approvals/export', { params, responseType: 'blob' }),
};

export const adminAPI = {
  getDashboard: () => apiClient.get('/admin/dashboard'),
  globalSearch: (q, limit = 20) => apiClient.get('/admin/search', { params: { q, limit } }),
  getPendingVerificationDocuments: (hours = 24, clientId = null, limit = 50, skip = 0) =>
    apiClient.get('/admin/documents/pending-verification', { params: { hours, client_id: clientId || undefined, limit, skip } }),
  getClients: (skip = 0, limit = 50) => apiClient.get('/admin/clients', { params: { skip, limit } }),
  getClientDetail: (clientId) => apiClient.get(`/admin/clients/${clientId}`),
  getClientControlPanel: (clientId) => apiClient.get(`/admin/clients/${clientId}/control-panel`),
  resendActivationEmail: (clientId) => apiClient.post(`/admin/clients/${clientId}/actions/resend-activation-email`),
  resendDashboardEmail: (clientId) => apiClient.post(`/admin/clients/${clientId}/actions/resend-dashboard-email`),
  recalculateCompliance: (clientId) => apiClient.post(`/admin/clients/${clientId}/actions/recalculate-compliance`),
  runClientJob: (clientId, job = 'compliance_recalc_client') => apiClient.post(`/admin/clients/${clientId}/actions/run-job`, { job }),
  unlockClientAccount: (clientId) => apiClient.post(`/admin/clients/${clientId}/actions/unlock-account`),
  startClientImpersonation: (clientId, ttlMinutes = 30) =>
    apiClient.post(`/admin/clients/${clientId}/impersonation/start`, null, { params: { ttl_minutes: ttlMinutes } }),
  getClientReceipts: (clientId, params = {}) => apiClient.get(`/admin/billing/clients/${clientId}/receipts`, { params }),
  resendClientReceipt: (clientId, body) => apiClient.post(`/admin/billing/clients/${clientId}/receipts/resend`, body),
  getAuditLogs: (skip = 0, limit = 100, clientId = null) => 
    apiClient.get('/admin/audit-logs', { params: { skip, limit, client_id: clientId } }),
  getEmailDelivery: (params = {}) =>
    apiClient.get('/admin/email-delivery', { params: { limit: 50, skip: 0, since_hours: 72, ...params } }),
  resendPasswordSetup: (clientId) => apiClient.post(`/admin/clients/${clientId}/resend-password-setup`),
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
  runJobNow: (jobId) => apiClient.post('/admin/jobs/run', { job: jobId }),
  // Operations & Compliance
  getOpsOverview: () => apiClient.get('/admin/ops/overview'),
  /** Admin priority actions (action queue / operational priorities). */
  getPriorityActions: (params = {}) => apiClient.get('/admin/ops/priority-actions', { params }),
  getClientFeatureFlags: (clientId) => apiClient.get(`/admin/ops/clients/${clientId}/feature-flags`),
  updateClientFeatureFlags: (clientId, updates) =>
    apiClient.patch(`/admin/ops/clients/${clientId}/feature-flags`, { updates }),
  getClientPlanUsage: (clientId) => apiClient.get(`/admin/ops/clients/${clientId}/plan-usage`),
  // Contractors (Ops Contractor Network)
  getContractors: (params = {}) => apiClient.get('/admin/ops/contractors', { params }),
  getContractorAnalytics: (params = {}) => apiClient.get('/admin/ops/contractors/analytics', { params }),
  getContractor: (contractorId) => apiClient.get(`/admin/ops/contractors/${contractorId}`),
  getContractorExplanation: (contractorId) => apiClient.get(`/admin/ops/contractors/${encodeURIComponent(contractorId)}/explanation`),
  createContractor: (body) => apiClient.post('/admin/ops/contractors', body),
  createNetworkContractor: (body) => apiClient.post('/admin/ops/contractors/network', body),
  approveContractor: (contractorId) => apiClient.patch(`/admin/ops/contractors/${contractorId}/approve`),
  updateContractor: (contractorId, body) => apiClient.patch(`/admin/ops/contractors/${contractorId}`, body),
  deleteContractor: (contractorId) => apiClient.delete(`/admin/ops/contractors/${contractorId}`),
  // Work orders (Ops Maintenance)
  getWorkOrders: (params = {}) => apiClient.get('/admin/ops/work-orders', { params }),
  getWorkOrder: (workOrderId) => apiClient.get(`/admin/ops/work-orders/${workOrderId}`),
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
    getProfile: () => apiClient.get('/contractor/profile', { headers }),
    getInvoices: (params = {}) => apiClient.get('/contractor/invoices', { params, headers }),
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
  };
}
