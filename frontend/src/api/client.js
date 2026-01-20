import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

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

// Response interceptor for global error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
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
  lookupPostcode: (postcode) => apiClient.get(`/intake/postcode-lookup/${encodeURIComponent(postcode)}`),
  uploadDocument: (formData) => apiClient.post('/intake/upload-document', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
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
  getClients: (skip = 0, limit = 50) => apiClient.get('/admin/clients', { params: { skip, limit } }),
  getClientDetail: (clientId) => apiClient.get(`/admin/clients/${clientId}`),
  getAuditLogs: (skip = 0, limit = 100, clientId = null) => 
    apiClient.get('/admin/audit-logs', { params: { skip, limit, client_id: clientId } }),
  resendPasswordSetup: (clientId) => apiClient.post(`/admin/clients/${clientId}/resend-password-setup`),
};
