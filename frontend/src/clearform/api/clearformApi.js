/**
 * ClearForm API Client
 * 
 * Handles all communication with ClearForm backend endpoints.
 */

const API_BASE = process.env.REACT_APP_BACKEND_URL;

// Token management
let authToken = localStorage.getItem('clearform_token');

export const setAuthToken = (token) => {
  authToken = token;
  if (token) {
    localStorage.setItem('clearform_token', token);
  } else {
    localStorage.removeItem('clearform_token');
  }
};

export const getAuthToken = () => authToken || localStorage.getItem('clearform_token');

const headers = () => ({
  'Content-Type': 'application/json',
  ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
});

// ============================================================================
// Auth API
// ============================================================================

export const authApi = {
  register: async (data) => {
    const res = await fetch(`${API_BASE}/api/clearform/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Registration failed');
    setAuthToken(json.access_token);
    return json;
  },

  login: async (email, password) => {
    const res = await fetch(`${API_BASE}/api/clearform/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Login failed');
    setAuthToken(json.access_token);
    return json;
  },

  getMe: async () => {
    const res = await fetch(`${API_BASE}/api/clearform/auth/me`, { headers: headers() });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to get user');
    return json;
  },

  logout: () => {
    setAuthToken(null);
  },
};

// ============================================================================
// Credits API
// ============================================================================

export const creditsApi = {
  getWallet: async () => {
    const res = await fetch(`${API_BASE}/api/clearform/credits/wallet`, { headers: headers() });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to get wallet');
    return json;
  },

  getBalance: async () => {
    const res = await fetch(`${API_BASE}/api/clearform/credits/balance`, { headers: headers() });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to get balance');
    return json;
  },

  getHistory: async (limit = 50, offset = 0) => {
    const res = await fetch(`${API_BASE}/api/clearform/credits/history?limit=${limit}&offset=${offset}`, {
      headers: headers(),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to get history');
    return json;
  },

  getPackages: async () => {
    const res = await fetch(`${API_BASE}/api/clearform/credits/packages`);
    return res.json();
  },

  createPurchase: async (packageId) => {
    const res = await fetch(`${API_BASE}/api/clearform/credits/purchase`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ package_id: packageId }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to create purchase');
    return json;
  },
};

// ============================================================================
// Documents API
// ============================================================================

export const documentsApi = {
  getTypes: async () => {
    const res = await fetch(`${API_BASE}/api/clearform/documents/types`);
    return res.json();
  },

  generate: async (data) => {
    const res = await fetch(`${API_BASE}/api/clearform/documents/generate`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(data),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to generate document');
    return json;
  },

  getVault: async (page = 1, pageSize = 20, filters = {}) => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      ...(filters.document_type && { document_type: filters.document_type }),
      ...(filters.status && { status: filters.status }),
      ...(filters.search && { search: filters.search }),
    });
    const res = await fetch(`${API_BASE}/api/clearform/documents/vault?${params}`, { headers: headers() });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to get vault');
    return json;
  },

  getDocument: async (documentId) => {
    const res = await fetch(`${API_BASE}/api/clearform/documents/${documentId}`, { headers: headers() });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to get document');
    return json;
  },

  archiveDocument: async (documentId) => {
    const res = await fetch(`${API_BASE}/api/clearform/documents/${documentId}`, {
      method: 'DELETE',
      headers: headers(),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to archive document');
    return json;
  },
};

// ============================================================================
// Subscriptions API
// ============================================================================

export const subscriptionsApi = {
  getPlans: async () => {
    const res = await fetch(`${API_BASE}/api/clearform/subscriptions/plans`);
    return res.json();
  },

  getCurrent: async () => {
    const res = await fetch(`${API_BASE}/api/clearform/subscriptions/current`, { headers: headers() });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to get subscription');
    return json;
  },

  subscribe: async (plan) => {
    const res = await fetch(`${API_BASE}/api/clearform/subscriptions/subscribe`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ plan }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to create subscription');
    return json;
  },

  cancel: async () => {
    const res = await fetch(`${API_BASE}/api/clearform/subscriptions/cancel`, {
      method: 'POST',
      headers: headers(),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Failed to cancel subscription');
    return json;
  },
};
