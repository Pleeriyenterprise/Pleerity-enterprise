/**
 * Outcome-based primary actions for client portal.
 * When backend supplies operational_cognition or operational_continuation, those are authoritative.
 */
import { getOperationalCognition, heroPrimaryFromCognition } from './operationalCognition';

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
  const fromCognition = heroPrimaryFromCognition(getOperationalCognition(signal));
  if (fromCognition?.label) {
    return {
      key: normalizeOperationalPrimaryKey(fromCognition.key || 'next_action'),
      label: fromCognition.label,
      url: fromCognition.url,
      continuation: fromCognition.continuation,
    };
  }
  const cont = signal?.operational_continuation;
  if (cont?.has_active_lineage && cont?.continuation_cta) {
    const cta = cont.continuation_cta;
    return {
      key: normalizeOperationalPrimaryKey(cta.key || 'view_workflow'),
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
 * Normalize server cognition primary keys to client executor keys.
 * @param {string} key
 */
export function normalizeOperationalPrimaryKey(key) {
  const k = String(key || '').trim();
  const map = {
    create_work_order: 'maintenance_job',
    schedule_inspection: 'compliance_inspection',
    create_issue: 'maintenance_issue',
    assign_contractor: 'assign_contractor',
    assign: 'assign_contractor',
  };
  return map[k] || k;
}

/**
 * @param {Record<string, unknown>|null|undefined} issue
 * @returns {{ key: string, label: string, url?: string, continuation?: boolean }|null}
 */
export function resolveIssuePrimaryAction(issue) {
  const fromCognition = heroPrimaryFromCognition(getOperationalCognition(issue));
  if (fromCognition?.label) {
    return {
      key: normalizeOperationalPrimaryKey(fromCognition.key || 'next_action'),
      label: fromCognition.label,
      url: fromCognition.url,
      continuation: fromCognition.continuation,
    };
  }
  const cont = issue?.operational_continuation;
  if (cont?.has_active_lineage && cont?.continuation_cta) {
    const cta = cont.continuation_cta;
    return {
      key: normalizeOperationalPrimaryKey(cta.key || 'view_workflow'),
      label: cta.label || OUTCOME_PRIMARY.viewWorkflow,
      url: cta.url,
      continuation: true,
    };
  }
  const st = String(issue?.status || '').toLowerCase();
  const linkedWo =
    issue?.linked_work_order_id ||
    issue?.operational_continuation?.existing_work_order_id;
  if (st === 'ready_for_work_order' && linkedWo) {
    return {
      key: 'assign_contractor',
      label: 'Assign contractor',
      url: `/operations/jobs/${linkedWo}`,
      continuation: true,
    };
  }
  if (
    issue &&
    st !== 'closed' &&
    st !== 'cancelled' &&
    !linkedWo
  ) {
    return { key: 'maintenance_job', label: 'Create maintenance job' };
  }
  return null;
}
