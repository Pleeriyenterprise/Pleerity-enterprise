import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Runtime debug: log backend URL once; expose for debug panel
if (typeof window !== 'undefined') {
  window.__CVP_BACKEND_URL = API_URL ?? '(not set)';
  console.log('[CVP] REACT_APP_BACKEND_URL:', window.__CVP_BACKEND_URL);
  if (!API_URL) {
    console.warn('[CVP] REACT_APP_BACKEND_URL is not set; API calls will fail.');
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
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: add auth token + dev log first request (endpoint + Authorization)
let firstRequestLogged = false;
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
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
    return response;
  },
  (error) => {
    const url = error.config?.url ?? error.config?.baseURL ?? '?';
    const status = error.response?.status;
    const data = error.response?.data;
    const detail = data?.detail;
    const message = (typeof detail === 'string' ? detail : detail?.message) ?? error.message ?? 'Network error';
    logApiRequest(url, status, message);
    setLastApiError(status, typeof message === 'string' ? message : JSON.stringify(detail ?? message));
    // Plan-gate 403: attach so UI can show upgrade state instead of crashing
    if (status === 403 && data && (data.upgrade_required === true || data.feature || data.feature_key)) {
      error.isPlanGateDenied = true;
      error.upgradeDetail = typeof detail === 'object' ? detail : { message, feature: data.feature ?? data.feature_key, upgrade_required: true };
    }
    if (status === 401) {
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
  setPassword: (data) => apiClient.post('/auth/set-password', data),
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
    apiClient.post('/intake/validate-property-count', { plan_id: planId, property_count: propertyCount })
};

export const clientAPI = {
  getDashboard: () => apiClient.get('/client/dashboard'),
  getEntitlements: () => apiClient.get('/client/entitlements'),
  getProperties: () => apiClient.get('/client/properties'),
  getPropertyRequirements: (propertyId) => apiClient.get(`/client/properties/${propertyId}/requirements`),
  getRequirements: () => apiClient.get('/client/requirements'),
  getDocuments: () => apiClient.get('/documents'),
};

export const adminAPI = {
  getDashboard: () => apiClient.get('/admin/dashboard'),
  getPendingVerificationDocuments: (hours = 24, clientId = null, limit = 50, skip = 0) =>
    apiClient.get('/admin/documents/pending-verification', { params: { hours, client_id: clientId || undefined, limit, skip } }),
  getClients: (skip = 0, limit = 50) => apiClient.get('/admin/clients', { params: { skip, limit } }),
  getClientDetail: (clientId) => apiClient.get(`/admin/clients/${clientId}`),
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
};
