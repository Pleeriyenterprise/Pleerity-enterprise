/**
 * Order Labels Utility - Maps internal codes to user-friendly display labels
 * 
 * Used throughout the admin UI to prevent leaking internal implementation details.
 */

// Service category mapping
export const CATEGORY_LABELS = {
  ai_automation: 'AI & Automation',
  market_research: 'Market Research',
  compliance: 'Compliance Services',
  document_pack: 'Document Packs',
  subscription: 'Subscription',
  // Fallback pattern
  default: 'Service',
};

// Service code to friendly name mapping
export const SERVICE_LABELS = {
  // AI & Automation
  AI_WORKFLOW: 'AI Workflow Blueprint',
  AI_WF_BLUEPRINT: 'AI Workflow Blueprint',
  AI_PROC_MAP: 'AI Process Mapping',
  AI_TOOL_REPORT: 'AI Tool Analysis Report',
  
  // Market Research
  MR_BASIC: 'Basic Market Research',
  MR_ADV: 'Advanced Market Research',
  
  // Compliance
  HMO_AUDIT: 'HMO Compliance Audit',
  FULL_AUDIT: 'Full Property Audit',
  MOVE_CHECKLIST: 'Move-in Checklist',
  
  // Document Packs
  DOC_PACK_ESSENTIAL: 'Essential Document Pack',
  DOC_PACK_PLUS: 'Plus Document Pack',
  DOC_PACK_PRO: 'Professional Document Pack',
};

// Status labels (more readable versions)
export const STATUS_LABELS = {
  CREATED: 'Created',
  PAID: 'Paid',
  QUEUED: 'Queued',
  IN_PROGRESS: 'In Progress',
  DRAFT_READY: 'Draft Ready',
  INTERNAL_REVIEW: 'Internal Review',
  REGEN_REQUESTED: 'Regeneration Requested',
  REGENERATING: 'Regenerating',
  CLIENT_INPUT_REQUIRED: 'Client Input Required',
  FINALISING: 'Finalising',
  DELIVERING: 'Delivering',
  COMPLETED: 'Completed',
  DELIVERY_FAILED: 'Delivery Failed',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
};

/**
 * Get friendly category label from internal code
 * @param {string} categoryCode - Internal category code (e.g., 'ai_automation')
 * @returns {string} User-friendly label
 */
export const getCategoryLabel = (categoryCode) => {
  if (!categoryCode) return 'Unknown';
  return CATEGORY_LABELS[categoryCode.toLowerCase()] || 
         categoryCode.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

/**
 * Get friendly service label from internal code
 * @param {string} serviceCode - Internal service code (e.g., 'AI_WORKFLOW')
 * @returns {string} User-friendly label
 */
export const getServiceLabel = (serviceCode) => {
  if (!serviceCode) return 'Unknown Service';
  return SERVICE_LABELS[serviceCode.toUpperCase()] || 
         serviceCode.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

/**
 * Get friendly status label from internal status
 * @param {string} status - Internal status code
 * @returns {string} User-friendly label
 */
export const getStatusLabel = (status) => {
  if (!status) return 'Unknown';
  return STATUS_LABELS[status.toUpperCase()] || 
         status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

export default {
  CATEGORY_LABELS,
  SERVICE_LABELS,
  STATUS_LABELS,
  getCategoryLabel,
  getServiceLabel,
  getStatusLabel,
};
