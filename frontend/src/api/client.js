import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Log API base URL once for live debug (non-sensitive)
if (typeof window !== 'undefined') {
  const base = API_URL ? `${API_URL}/api` : '(not set)';
  console.log('[CVP] API base URL:', base);
  if (!API_URL) {
    console.warn('[CVP] REACT_APP_BACKEND_URL is not set; API calls will fail.');
  }
}

const apiClient = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: 401 → session expired flow (clear message on login page)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user');
      window.location.href = '/login?session_expired=1';
    }
    return Promise.reject(error);
  }
);

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
