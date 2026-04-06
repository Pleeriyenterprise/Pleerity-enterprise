/**
 * Fire-and-forget contractor workflow usage beacons (never blocks UI).
 * Backend persists audit rows with contractor_id, work_order_id, timestamp.
 */

/**
 * @param {(body: object) => Promise<unknown>} postWorkflowUsage - api.postWorkflowUsage from createContractorAPI / createJobLinkAPI
 * @param {{ event_type: string, work_order_id: string, action_id?: string }} payload
 */
export function fireContractorWorkflowUsage(postWorkflowUsage, payload) {
  if (typeof postWorkflowUsage !== 'function' || !payload?.work_order_id || !payload?.event_type) return;
  try {
    postWorkflowUsage(payload).catch(() => {});
  } catch {
    /* ignore */
  }
}
