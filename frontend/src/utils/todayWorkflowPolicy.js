/**
 * Today page — pure UI workflow classification and business-action shaping.
 * Does not call APIs; uses existing task fields only (see today_projection_service.py).
 */

import { resolveClientPortalPath } from './clientPortalNavigation';

/** @typedef {'compliance'|'compliance_job'|'maintenance_job'|'maintenance'|'issue_risk'|'approval'|'unclear'} TodayWorkflow */

/**
 * @param {Record<string, unknown>|null|undefined} task
 * @returns {TodayWorkflow}
 */
export function classifyTodayTaskWorkflow(task) {
  if (!task || typeof task !== 'object') return 'unclear';
  const st = String(task.source_type || '').toLowerCase();
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const wok = String(meta.work_order_kind || '').toUpperCase();
  const pat = String(task.primary_action_type || task.action_context_type || '').toLowerCase();

  if (st === 'approval') return 'approval';
  if (st === 'risk_signal' || pat === 'risk_follow_up') return 'issue_risk';
  if (st === 'issue') return 'maintenance';
  if (st === 'work_order') return wok === 'COMPLIANCE' ? 'compliance_job' : 'maintenance_job';
  if (st === 'requirement' || st === 'tenant_request') return 'compliance';
  return 'unclear';
}

const ALLOWED_BY_WORKFLOW = {
  compliance: new Set([
    'upload_certificate',
    'create_compliance_work_order',
    'view_requirement',
    'open_primary',
  ]),
  compliance_job: new Set(['view_job', 'open_primary']),
  maintenance_job: new Set(['view_job', 'open_primary']),
  maintenance: new Set(['create_maintenance_job', 'view_issue', 'open_primary']),
  issue_risk: new Set(['review_risk_signal', 'open_primary']),
  approval: new Set(['view_approval', 'open_primary']),
  unclear: new Set([
    'upload_certificate',
    'create_compliance_work_order',
    'view_requirement',
    'view_job',
    'view_issue',
    'review_risk_signal',
    'view_approval',
    'create_maintenance_job',
    'open_primary',
  ]),
};

const ORDER_BY_WORKFLOW = {
  /** Upload-first so document gaps beat synthetic “create job” when both are eligible. */
  compliance: ['upload_certificate', 'create_compliance_work_order', 'view_requirement', 'open_primary'],
  compliance_job: ['view_job', 'open_primary'],
  maintenance_job: ['view_job', 'open_primary'],
  maintenance: ['create_maintenance_job', 'view_issue', 'open_primary'],
  issue_risk: ['review_risk_signal', 'open_primary'],
  approval: ['view_approval', 'open_primary'],
  unclear: [
    'upload_certificate',
    'create_compliance_work_order',
    'view_requirement',
    'review_risk_signal',
    'view_approval',
    'create_maintenance_job',
    'view_issue',
    'view_job',
    'open_primary',
  ],
};

/**
 * @param {TodayWorkflow} wf
 * @param {string} id
 */
function rankAction(wf, id) {
  const order = ORDER_BY_WORKFLOW[wf] || ORDER_BY_WORKFLOW.unclear;
  const i = order.indexOf(id);
  return i === -1 ? 999 : i;
}

/**
 * Merge eligibility-driven compliance job creation when absent from capped API actions.
 * @param {Record<string, unknown>} task
 * @param {TodayWorkflow} workflow
 * @param {Array<Record<string, unknown>>} ordered
 * @param {boolean} showComplianceBooking
 */
export function mergeComplianceCreateIfEligible(task, workflow, ordered, showComplianceBooking) {
  if (workflow !== 'compliance' || !showComplianceBooking) return ordered;
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const ce = meta.compliance_execution_booking;
  if (!ce || !ce.eligible || !ce.linked_property_requirement_id) return ordered;
  if (ordered.some((a) => String(a.id) === 'create_compliance_work_order')) return ordered;
  const synth = {
    id: 'create_compliance_work_order',
    label: 'Fix compliance issue',
    requirement_id: ce.linked_property_requirement_id,
    property_id: ce.property_id || task.property_id,
    requirement_code: ce.requirement_code,
    compliance_purpose: ce.compliance_purpose || 'inspection',
    compliance_generated_from: ce.compliance_generated_from || 'requirement',
  };
  return [synth, ...ordered];
}

/**
 * Filter and order `business_actions` for Today cards (workflow separation, single-primary shaping).
 * @param {Record<string, unknown>} task
 * @param {Array<Record<string, unknown>>|null|undefined} businessActions
 * @param {boolean} showComplianceBooking
 * @returns {{ workflow: TodayWorkflow, ordered: Array<Record<string, unknown>> }}
 */
export function shapeTodayBusinessActions(task, businessActions, showComplianceBooking) {
  const workflow = classifyTodayTaskWorkflow(task);
  const allowed = ALLOWED_BY_WORKFLOW[workflow] || ALLOWED_BY_WORKFLOW.unclear;
  const raw = Array.isArray(businessActions) ? businessActions : [];
  const filtered = raw.filter((a) => allowed.has(String(a.id || '')));
  const wf = workflow;
  filtered.sort(
    (a, b) =>
      rankAction(wf, String(a.id || '')) - rankAction(wf, String(b.id || '')) ||
      String(a.label || '').localeCompare(String(b.label || '')),
  );
  let ordered = mergeComplianceCreateIfEligible(task, wf, filtered, showComplianceBooking);
  ordered.sort(
    (a, b) =>
      rankAction(wf, String(a.id || '')) - rankAction(wf, String(b.id || '')) ||
      String(a.label || '').localeCompare(String(b.label || '')),
  );
  return { workflow, ordered };
}

/**
 * Resolved path for comparing Continue vs primary (navigate-only actions).
 * @param {Record<string, unknown>|null|undefined} act
 * @param {string} fallbackPrefix
 */
export function businessActionNavigatePath(act, fallbackPrefix = '/today') {
  if (!act || typeof act !== 'object') return '';
  const nav = act.navigate;
  if (nav == null || nav === '') return '';
  return resolveClientPortalPath(String(nav), fallbackPrefix);
}

/**
 * Strip trailing parenthetical snake_case tokens from inbox titles (e.g. compliance codes).
 * @param {string} s
 */
export function stripTechnicalParenTail(s) {
  let t = String(s || '').trim();
  let prev = '';
  while (t !== prev) {
    prev = t;
    t = t.replace(/\s*\(([a-z][a-z0-9_]*)\)\s*$/i, '').trim();
  }
  return t;
}
