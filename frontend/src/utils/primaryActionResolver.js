/**
 * Outcome-based primary actions for client portal (no API contract changes).
 * Classifies risk signals and normalises labels away from internal workflow verbs.
 * Labels describe the next operational step only — not compliance restoration (Stream C/E).
 */

export const OUTCOME_PRIMARY = {
  /** Compliance inspection path (schedule_inspection + compliance engine). */
  startInspectionJob: 'Start inspection job',
  /** Schedule inspection when compliance engine is off — logs/trips inspection issue flow. */
  logInspectionIssue: 'Log maintenance issue',
  startMaintenanceJob: 'Start maintenance job',
  logMaintenanceIssue: 'Log maintenance issue',
  reviewRiskSignal: 'Review risk signal',
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
    return { key: 'compliance_inspection', label: OUTCOME_PRIMARY.startInspectionJob };
  }
  if (wantInspection && !hasComplianceEngine) {
    return { key: 'log_inspection_issue', label: OUTCOME_PRIMARY.logInspectionIssue };
  }
  if (actions.includes('create_work_order')) {
    return { key: 'maintenance_job', label: OUTCOME_PRIMARY.startMaintenanceJob };
  }
  if (actions.includes('create_issue')) {
    return { key: 'maintenance_issue', label: OUTCOME_PRIMARY.logMaintenanceIssue };
  }
  return { key: 'review', label: OUTCOME_PRIMARY.reviewRiskSignal };
}
