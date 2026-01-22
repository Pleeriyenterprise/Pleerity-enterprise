/**
 * Orders API Client - Centralized API calls for the Orders & Workflow System.
 * 
 * This module provides a single source of truth for all order-related API calls,
 * integrating with both the legacy admin orders API and the new V2 orchestration system.
 */

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Get auth headers with token from localStorage
 */
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
};

/**
 * Handle API response and throw on error
 */
const handleResponse = async (response) => {
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.message || 'API request failed');
  }
  return data;
};

// =============================================================================
// PIPELINE & LIST OPERATIONS
// =============================================================================

export const ordersApi = {
  /**
   * Get orders for pipeline view with counts by status
   */
  getPipeline: async (status = null, limit = 50, skip = 0) => {
    const params = new URLSearchParams({ limit, skip });
    if (status) params.append('status', status);
    
    const response = await fetch(
      `${API_URL}/api/admin/orders/pipeline?${params}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Get pipeline status counts only (for badge updates)
   */
  getPipelineCounts: async () => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/pipeline/counts`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Search orders by query, status, or category
   */
  searchOrders: async (q = null, status = null, serviceCategory = null, limit = 50, skip = 0) => {
    const params = new URLSearchParams({ limit, skip });
    if (q) params.append('q', q);
    if (status) params.append('status', status);
    if (serviceCategory) params.append('service_category', serviceCategory);
    
    const response = await fetch(
      `${API_URL}/api/admin/orders/search?${params}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // ORDER DETAIL OPERATIONS
  // =============================================================================

  /**
   * Get full order details including timeline
   */
  getOrderDetail: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Get order timeline only
   */
  getOrderTimeline: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/timeline`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // STATE TRANSITIONS
  // =============================================================================

  /**
   * Transition order to a new status (manual)
   */
  transitionOrder: async (orderId, newStatus, reason, notes = null) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/transition`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ new_status: newStatus, reason, notes }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Approve order and lock document version (INTERNAL_REVIEW → FINALISING)
   */
  approveOrder: async (orderId, version, notes = null) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/approve`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ version, notes }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Request regeneration with structured feedback
   */
  requestRegeneration: async (orderId, reason, correctionNotes, affectedSections = null, guardrails = null) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/request-regen`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          reason,
          correction_notes: correctionNotes,
          affected_sections: affectedSections,
          guardrails,
        }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Request more information from client (pause SLA, send email)
   */
  requestClientInfo: async (orderId, requestNotes, requestedFields = null, deadlineDays = null, requestAttachments = false) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/request-info`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          request_notes: requestNotes,
          requested_fields: requestedFields,
          deadline_days: deadlineDays,
          request_attachments: requestAttachments,
        }),
      }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // DOCUMENT OPERATIONS
  // =============================================================================

  /**
   * Get all document versions for an order
   */
  getDocumentVersions: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/documents`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Trigger document generation (legacy endpoint)
   */
  generateDocuments: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/generate-documents`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      }
    );
    return handleResponse(response);
  },

  /**
   * Get document preview URL (returns URL, not fetched directly)
   */
  getDocumentPreviewUrl: (orderId, version, format = 'pdf') => {
    return `${API_URL}/api/admin/orders/${orderId}/documents/${version}/preview?format=${format}`;
  },

  /**
   * Download document (opens in new tab with auth)
   */
  downloadDocument: (orderId, version, format = 'pdf') => {
    const url = `${API_URL}/api/admin/orders/${orderId}/documents/${version}/preview?format=${format}`;
    window.open(url, '_blank');
  },

  // =============================================================================
  // V2 ORCHESTRATION INTEGRATION
  // =============================================================================

  /**
   * Generate documents via the new V2 orchestration pipeline
   * This triggers the full pipeline: snapshot → GPT → render → ready for review
   */
  orchestrateGeneration: async (orderId, intakeData) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/generate`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          order_id: orderId,
          intake_data: intakeData,
        }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Regenerate documents via V2 orchestration with notes
   */
  orchestrateRegeneration: async (orderId, intakeData, regenerationNotes) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/regenerate`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          order_id: orderId,
          intake_data: intakeData,
          regeneration_notes: regenerationNotes,
        }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Submit review via orchestration (approve or reject)
   */
  orchestrateReview: async (orderId, approved, reviewNotes = null) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/review`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          order_id: orderId,
          approved,
          review_notes: reviewNotes,
        }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Get orchestration document versions (with hashes)
   */
  getOrchestrationVersions: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/versions/${orderId}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Get specific document version from orchestration
   */
  getOrchestrationVersion: async (orderId, version) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/versions/${orderId}/${version}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Get generation history for an order
   */
  getGenerationHistory: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/history/${orderId}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Get latest generation execution
   */
  getLatestGeneration: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/latest/${orderId}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Validate intake data before generation
   */
  validateIntakeData: async (serviceCode, intakeData) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/validate-data?service_code=${encodeURIComponent(serviceCode)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(intakeData),
      }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // DELIVERY OPERATIONS
  // =============================================================================

  /**
   * Trigger delivery for a FINALISING order
   */
  deliverOrder: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/deliver`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      }
    );
    return handleResponse(response);
  },

  /**
   * Retry delivery for a DELIVERY_FAILED order
   */
  retryDelivery: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/retry-delivery`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      }
    );
    return handleResponse(response);
  },

  /**
   * Manually complete an order (admin override)
   */
  manualComplete: async (orderId, reason) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/manual-complete`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Process all pending deliveries (batch)
   */
  processAllDeliveries: async () => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/batch/process-delivery`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      }
    );
    return handleResponse(response);
  },

  // =============================================================================
  // ADMIN ACTIONS
  // =============================================================================

  /**
   * Cancel order (pre-payment only)
   */
  cancelOrder: async (orderId, reason) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/cancel`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Archive order (soft removal from pipeline)
   */
  archiveOrder: async (orderId, reason) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/archive`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Unarchive order
   */
  unarchiveOrder: async (orderId) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/unarchive`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      }
    );
    return handleResponse(response);
  },

  /**
   * Rollback order to previous safe state
   */
  rollbackOrder: async (orderId, reason) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/rollback`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Reopen a locked approved order for editing
   */
  reopenOrder: async (orderId, reason) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/reopen`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Set or remove priority flag
   */
  setPriority: async (orderId, priority, reason = null) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/priority`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ priority, reason }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Add internal note to order
   */
  addNote: async (orderId, note) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/notes`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ note }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Resend client info request
   */
  resendRequest: async (orderId, note) => {
    const response = await fetch(
      `${API_URL}/api/admin/orders/${orderId}/resend-request`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ note }),
      }
    );
    return handleResponse(response);
  },
};

// =============================================================================
// SERVICES API (V2)
// =============================================================================

export const servicesApi = {
  /**
   * Get all public services from V2 catalogue
   */
  getPublicServices: async () => {
    const response = await fetch(
      `${API_URL}/api/v2/public/services`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Get service details by code
   */
  getServiceDetails: async (serviceCode) => {
    const response = await fetch(
      `${API_URL}/api/v2/public/services/${serviceCode}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Calculate price with add-ons
   */
  calculatePrice: async (serviceCode, variantCode, addons = []) => {
    const response = await fetch(
      `${API_URL}/api/v2/public/services/calculate-price`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          service_code: serviceCode,
          variant_code: variantCode,
          addons,
        }),
      }
    );
    return handleResponse(response);
  },

  /**
   * Get admin service stats
   */
  getAdminStats: async () => {
    const response = await fetch(
      `${API_URL}/api/v2/admin/services/stats`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },

  /**
   * Get prompt definition for a service
   */
  getPromptDefinition: async (serviceCode) => {
    const response = await fetch(
      `${API_URL}/api/orchestration/validate/${serviceCode}`,
      { headers: getAuthHeaders() }
    );
    return handleResponse(response);
  },
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Format price from pence to pounds
 */
export const formatPrice = (pence) => {
  if (typeof pence !== 'number') return '£0.00';
  return `£${(pence / 100).toFixed(2)}`;
};

/**
 * Format price from pence to pounds (whole numbers if .00)
 */
export const formatPriceShort = (pence) => {
  if (typeof pence !== 'number') return '£0';
  const pounds = pence / 100;
  return pounds % 1 === 0 ? `£${pounds}` : `£${pounds.toFixed(2)}`;
};

export default ordersApi;
