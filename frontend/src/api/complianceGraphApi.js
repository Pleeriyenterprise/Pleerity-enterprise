/**
 * Compliance Evidence Graph — Graph Service API (Phase 3/4).
 * All access via Graph Service HTTP routes; no raw storage.
 */
import apiClient from './client';

export const complianceGraphAPI = {
  listDecisions: (params) => apiClient.get('/admin/compliance/graph/decisions', { params }),
  explainDecision: (decisionId) =>
    apiClient.get(`/admin/compliance/graph/decisions/${encodeURIComponent(decisionId)}/explain`),
  replayDecision: (decisionId) =>
    apiClient.get(`/admin/compliance/graph/decisions/${encodeURIComponent(decisionId)}/replay`),
  compareDecisions: (left, right) =>
    apiClient.get('/admin/compliance/graph/decisions/compare', { params: { left, right } }),
  compareSnapshots: (left, right) =>
    apiClient.get('/admin/compliance/graph/snapshots/compare', { params: { left, right } }),
  explainScope: (params) => apiClient.get('/admin/compliance/graph/explain-scope', { params }),
  traceRequirement: (requirementId, clientId) =>
    apiClient.get(`/admin/compliance/graph/requirements/${encodeURIComponent(requirementId)}/trace`, {
      params: { client_id: clientId },
    }),
  traceEvidence: (params) => apiClient.get('/admin/compliance/graph/evidence/trace', { params }),
  decisionDependencies: (decisionId) =>
    apiClient.get(`/admin/compliance/graph/decisions/${encodeURIComponent(decisionId)}/dependencies`),
  operationalImpact: (decisionId) =>
    apiClient.get(`/admin/compliance/graph/decisions/${encodeURIComponent(decisionId)}/operational-impact`),
  graphHealth: (params = {}) => apiClient.get('/admin/compliance/graph/health', { params }),
};

export default complianceGraphAPI;
