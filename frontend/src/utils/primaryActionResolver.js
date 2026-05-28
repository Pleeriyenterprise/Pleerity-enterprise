/**
 * Outcome-based primary actions for client portal.
 * When backend supplies operational_continuation, that is authoritative over create/start verbs.
 */

export const OUTCOME_PRIMARY = {
  startInspectionJob: 'Start inspection job',
  logInspectionIssue: 'Log maintenance issue',
  startMaintenanceJob: 'Start maintenance job',
  logMaintenanceIssue: 'Log maintenance issue',
  reviewRiskSignal: 'Review risk signal',
  viewWorkflow: 'View workflow',
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
 * @param {Record<string, unknown>|null|undefined} signal
 * @returns {{ key: string, label: string, url?: string, continuation?: boolean }}
 */
export function resolveRiskSignalPrimaryKey(signal, hasMaintenanceWorkflows, hasComplianceEngine) {
  const cont = signal?.operational_continuation;
  if (cont?.has_active_lineage && cont?.continuation_cta) {
    const cta = cont.continuation_cta;
    return {
      key: cta.key || 'view_workflow',
      label: cta.label || OUTCOME_PRIMARY.viewWorkflow,
      url: cta.url,
      continuation: true,
    };
  }
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

/**
 * @param {Record<string, unknown>|null|undefined} issue
 * @returns {{ key: string, label: string, url?: string, continuation?: boolean }|null}
 */
export function resolveIssuePrimaryAction(issue) {
  const cont = issue?.operational_continuation;
  if (cont?.has_active_lineage && cont?.continuation_cta) {
    const cta = cont.continuation_cta;
    return {
      key: cta.key || 'view_workflow',
      label: cta.label || OUTCOME_PRIMARY.viewWorkflow,
      url: cta.url,
      continuation: true,
    };
  }
  if (
    issue &&
    issue.status !== 'closed' &&
    issue.status !== 'cancelled' &&
    !issue.linked_work_order_id
  ) {
    return { key: 'create_work_order', label: 'Create maintenance job' };
  }
  return null;
}
