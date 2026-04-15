import { buildEntityRoute, resolveClientPortalPath } from './clientPortalNavigation';
import { resolveInboxTaskTakeActionRoute } from './requirementTakeActionResolver';

/**
 * Central CTA registry for client-portal task actions.
 * entity -> action -> route -> api hint -> audit hint
 */
const CTA_REGISTRY = {
  requirement: {
    upload_evidence: { routeMode: 'upload', api: 'uploadDocument', audit: 'DOCUMENT_UPLOADED' },
    review_requirement: { routeMode: 'requirement', api: 'openRequirement', audit: 'REQUIREMENT_ACTION_TRIGGERED' },
  },
  work_order: {
    work_order: { routeMode: 'review', api: 'openWorkOrder', audit: 'WORK_ORDER_OPENED' },
  },
  risk_signal: {
    risk_follow_up: { routeMode: 'review', api: 'openRiskSignal', audit: 'RISK_SIGNAL_OPENED' },
  },
  approval: {
    review_approval: { routeMode: 'review', api: 'openApproval', audit: 'APPROVAL_OPENED' },
  },
  tenant_request: {
    upload_evidence: { routeMode: 'upload', api: 'uploadDocument', audit: 'REQUIREMENT_ACTION_TRIGGERED' },
  },
};

function resolveActionType(task, which = 'primary') {
  if (which === 'secondary') return 'review_requirement';
  return String(task?.primary_action_type || task?.action_context_type || '').trim().toLowerCase();
}

export function resolveTaskCta(task, which = 'primary') {
  const sourceType = String(task?.source_type || task?.source_entity_type || '').trim().toLowerCase();
  const actionType = resolveActionType(task, which);
  const entry = (CTA_REGISTRY[sourceType] || {})[actionType];

  const requirementId =
    task?.requirement_id ||
    (task?.source_type === 'requirement' ? task?.source_id : null) ||
    task?.metadata?.related_requirement_id ||
    task?.metadata?.requirement_id;
  const propertyId = task?.property_id || task?.metadata?.property_id || task?.metadata?.related_property_id;
  const workOrderId =
    task?.work_order_id ||
    (task?.source_type === 'work_order' ? task?.source_id : null) ||
    task?.metadata?.related_work_order_id;

  const takeRoute = resolveInboxTaskTakeActionRoute(task, which === 'secondary' ? 'secondary' : 'primary');
  const strictRoute = takeRoute
    ? takeRoute
    : entry
      ? buildEntityRoute(
          {
            requirement_id: requirementId,
            property_id: propertyId,
            work_order_id: workOrderId,
            mode: entry.routeMode,
          },
          ''
        )
      : '';

  const fallbackRaw =
    which === 'secondary' ? task?.secondary_action_url || task?.primary_action_url : task?.primary_action_url;
  const fallback = which === 'secondary' ? '/today' : '/dashboard';

  return {
    route: strictRoute || resolveClientPortalPath(fallbackRaw, fallback),
    api: entry?.api || null,
    audit: entry?.audit || null,
    action_type: actionType || null,
    source_type: sourceType || null,
  };
}

