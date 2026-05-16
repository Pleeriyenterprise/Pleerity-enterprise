/**
 * Client toast + event helpers for canonical requirement action outcomes.
 * Aligns with backend ``workflow_complete`` / ``authority_synced`` on guided evidence responses.
 */
import { toast } from '@/utils/portalNotifications';

/**
 * @param {Record<string, unknown>|null|undefined} data API response body
 * @param {{ defaultSuccess?: string, defaultPartial?: string }} [opts]
 * @returns {boolean} true when the action fully completed (authority synced + enriched row)
 */
export function toastComplianceActionOutcome(data, opts = {}) {
  const defaultSuccess = opts.defaultSuccess || 'Requirement recorded and compliance status is updating.';
  const defaultPartial =
    opts.defaultPartial ||
    'Document uploaded, but requirement status could not be updated. Please refresh or contact support.';

  if (!data || typeof data !== 'object') {
    toast.error('Could not confirm requirement status. Please refresh.');
    return false;
  }

  const workflowComplete =
    data.workflow_complete === true ||
    (data.ok === true && data.authority_synced === true && Boolean(data.requirement));
  const msg = typeof data.message === 'string' && data.message.trim() ? data.message.trim() : null;

  if (workflowComplete) {
    toast.success(msg || defaultSuccess);
    return true;
  }
  if (data.ok === true) {
    toast.warning(msg || defaultPartial);
    return false;
  }
  toast.error(msg || 'Could not save requirement evidence.');
  return false;
}

/**
 * @param {string|null|undefined} propertyId
 * @param {Record<string, unknown>} [extra]
 */
export function dispatchComplianceOutcome(propertyId, extra = {}) {
  if (typeof window === 'undefined' || !propertyId) return;
  window.dispatchEvent(
    new CustomEvent('compliance-outcome', {
      detail: { property_id: String(propertyId), ...extra },
    }),
  );
}
