import apiClient from './client';

const BASE = '/admin/discovery/review';

export const discoveryApi = {
  getReviewQueue: (params = {}) => apiClient.get(`${BASE}/queue`, { params }),
  getReviewSummary: () => apiClient.get(`${BASE}/summary`),
  getReviewDetail: (prospectId) =>
    apiClient.get(`${BASE}/${encodeURIComponent(prospectId)}`),
  getAuditHistory: (prospectId, params = {}) =>
    apiClient.get(`${BASE}/${encodeURIComponent(prospectId)}/audit`, { params }),
  approveProspect: (prospectId, body) =>
    apiClient.post(`${BASE}/${encodeURIComponent(prospectId)}/approve`, body),
  rejectProspect: (prospectId, body) =>
    apiClient.post(`${BASE}/${encodeURIComponent(prospectId)}/reject`, body),
  requestChanges: (prospectId, body) =>
    apiClient.post(`${BASE}/${encodeURIComponent(prospectId)}/request-changes`, body),
  markDuplicate: (prospectId) =>
    apiClient.post(`${BASE}/${encodeURIComponent(prospectId)}/mark-duplicate`, {}),
  clearDuplicate: (prospectId, body = {}) =>
    apiClient.post(`${BASE}/${encodeURIComponent(prospectId)}/clear-duplicate`, body),
  archiveProspect: (prospectId) =>
    apiClient.post(`${BASE}/${encodeURIComponent(prospectId)}/archive`, {}),
};

export const isDiscoveryModuleEnabled = () =>
  process.env.REACT_APP_DISCOVERY_MODULE_ENABLED === 'true';

export default discoveryApi;
