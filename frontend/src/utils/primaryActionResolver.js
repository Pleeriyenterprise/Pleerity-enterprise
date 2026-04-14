/**
 * Outcome-based primary actions for client portal (no API contract changes).
 * Classifies flagged signals and normalises labels away from internal workflow verbs.
 */

export const OUTCOME_PRIMARY = {
  fixComplianceIssue: 'Fix compliance issue',
  fixIssue: 'Fix issue',
  reviewIssue: 'Review issue',
};

/**
 * @param {Record<string, unknown>|null|undefined} signal
 * @returns {'compliance'|'maintenance'|'informational'}
 */
export function classifyFlaggedSignal(signal) {
  const actions = Array.isArray(signal?.suggested_actions)
    ? signal.suggested_actions
    : ['create_issue', 'create_work_order'];
  if (actions.includes('schedule_inspection')) return 'compliance';
  if (actions.includes('create_work_order') || actions.includes('create_issue')) return 'maintenance';
  return 'informational';
}

/**
 * What the single primary button should be for a risk signal row (UI maps this to handlers).
 * @returns {{ key: string, label: string }}
 */
export function resolveRiskSignalPrimaryKey(signal, hasMaintenanceWorkflows, hasComplianceEngine) {
  const actions = Array.isArray(signal?.suggested_actions)
    ? signal.suggested_actions
    : ['create_issue', 'create_work_order'];
  const wantInspection = actions.includes('schedule_inspection') && hasMaintenanceWorkflows;
  if (wantInspection && hasComplianceEngine) {
    return { key: 'compliance_inspection', label: OUTCOME_PRIMARY.fixComplianceIssue };
  }
  if (wantInspection && !hasComplianceEngine) {
    return { key: 'log_inspection_issue', label: OUTCOME_PRIMARY.fixIssue };
  }
  if (actions.includes('create_work_order')) {
    return { key: 'maintenance_job', label: OUTCOME_PRIMARY.fixIssue };
  }
  if (actions.includes('create_issue')) {
    return { key: 'maintenance_issue', label: OUTCOME_PRIMARY.fixIssue };
  }
  return { key: 'review', label: OUTCOME_PRIMARY.reviewIssue };
}
