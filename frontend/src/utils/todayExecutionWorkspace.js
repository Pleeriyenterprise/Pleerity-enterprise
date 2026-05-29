/**
 * Today execution workspace — operational grouping and primary-action elevation.
 * Read-only projection; authority stays on server envelopes (operational_cognition, take_action, continuation).
 */
import { compareTopPriority } from './clientTopPriorityRanking';
import { buildRequirementShapedRowFromPriorityTask } from './taskRequirementRowAdapter';
import { inboxTaskLinkedRequirementId } from './portalRequirementAttention';
import {
  isRequirementPendingReviewAttention,
  isRequirementUrgentActionAttention,
  resolveClientRequirementLifecycle,
} from './clientRequirementLifecycle';
import { getOperationalCognition, heroPrimaryFromCognition } from './operationalCognition';
import { getPropertyDisplayName } from './propertyDisplayName';

/**
 * @param {Map<string, Record<string, unknown>>} propertyById
 */
export function buildPropertyByIdMap(propertyOptions) {
  const m = new Map();
  if (!Array.isArray(propertyOptions)) return m;
  for (const p of propertyOptions) {
    if (p?.property_id != null) m.set(String(p.property_id), p);
  }
  return m;
}

/**
 * Merge requirement cognition / continuation onto a task for hero + chips.
 * @param {Record<string, unknown>} task
 * @param {Map<string, Record<string, unknown>>} requirementsById
 * @param {Map<string, Record<string, unknown>>} propertyById
 */
export function enrichTaskForExecution(task, requirementsById, propertyById) {
  if (!task || typeof task !== 'object') return null;
  const shaped = buildRequirementShapedRowFromPriorityTask(task, requirementsById);
  const rid = inboxTaskLinkedRequirementId(task);
  const req = rid && requirementsById instanceof Map ? requirementsById.get(String(rid)) : null;
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};

  const entity = {
    ...(shaped || {}),
    ...task,
    ...(shaped ? { take_action: shaped.take_action || task.metadata?.take_action } : {}),
  };

  if (req?.operational_cognition) entity.operational_cognition = req.operational_cognition;
  if (req?.requirement_guidance_v1) entity.requirement_guidance_v1 = req.requirement_guidance_v1;
  if (meta.operational_continuation) entity.operational_continuation = meta.operational_continuation;

  const pid = task.property_id != null ? String(task.property_id) : '';
  const prop = pid && propertyById instanceof Map ? propertyById.get(pid) : null;
  entity.property_display_name =
    (prop ? getPropertyDisplayName(prop) : null) ||
    String(task.property_label || '').trim() ||
    null;

  return entity;
}

/**
 * Highest-confidence next action from existing urgent + upcoming + in-progress pool.
 */
export function pickPrimaryExecutionTask(tasks, requirementsById, propertyById) {
  if (!Array.isArray(tasks) || !tasks.length) return null;
  const sorted = [...tasks].sort(compareTopPriority);
  for (const t of sorted) {
    if (!t?.id) continue;
    const enriched = enrichTaskForExecution(t, requirementsById, propertyById);
    const cog = getOperationalCognition(enriched);
    if (cog && heroPrimaryFromCognition(cog)) return enriched;
    const ta = enriched?.take_action?.primary || enriched?.metadata?.take_action?.primary;
    if (ta?.label) return enriched;
  }
  return enrichTaskForExecution(sorted[0], requirementsById, propertyById);
}

/** @returns {'needs_action_now'|'waiting_on_others'|'in_progress'|'recently_completed'|'snoozed'} */
export function classifyTaskOperationalBucket(task, requirementsById) {
  if (!task) return 'needs_action_now';
  const src = String(task.source_type || '').toLowerCase();
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const rid = inboxTaskLinkedRequirementId(task);
  const req = rid && requirementsById instanceof Map ? requirementsById.get(String(rid)) : null;

  if (req && isRequirementPendingReviewAttention(req)) return 'waiting_on_others';
  if (src === 'approval' || String(task.primary_action_type || '').toLowerCase() === 'review_approval') {
    return 'waiting_on_others';
  }
  const woStatus = String(meta.work_order_status || meta.status || '').toUpperCase();
  if (src === 'work_order' && ['ASSIGNED', 'SCHEDULED', 'AWAITING_VISIT'].includes(woStatus)) {
    return 'waiting_on_others';
  }
  if (meta.operational_continuation?.has_active_lineage) return 'in_progress';

  const section = String(task.section || '').toLowerCase();
  if (section === 'recently_completed') return 'recently_completed';
  if (section === 'in_progress' || src === 'work_order') return 'in_progress';
  if (section === 'snoozed') return 'snoozed';

  if (req && !isRequirementUrgentActionAttention(req) && resolveClientRequirementLifecycle(req).state === 'SATISFIED_UNVERIFIED') {
    return 'waiting_on_others';
  }

  return 'needs_action_now';
}

/**
 * Operational section buckets for Today execution workspace.
 */
export function buildOperationalSections(sections, applyFilter, requirementsById) {
  const needsActionNow = [];
  const waitingOnOthers = [];
  const inProgress = [];
  const recentlyCompleted = [];
  const seen = new Set();

  const push = (bucket, task, sectionKey) => {
    if (!task?.id || seen.has(task.id)) return;
    seen.add(task.id);
    const classified = classifyTaskOperationalBucket({ ...task, section: sectionKey }, requirementsById);
    if (classified === 'waiting_on_others') waitingOnOthers.push(task);
    else if (classified === 'in_progress') inProgress.push(task);
    else if (classified === 'recently_completed') recentlyCompleted.push(task);
    else needsActionNow.push(task);
  };

  for (const t of applyFilter(sections.urgent || [])) push('needs', t, 'urgent');
  for (const t of applyFilter(sections.upcoming || [])) push('needs', t, 'upcoming');
  for (const t of applyFilter(sections.in_progress || [])) push('progress', t, 'in_progress');
  for (const t of applyFilter(sections.recently_completed || [])) push('done', t, 'recently_completed');

  return { needsActionNow, waitingOnOthers, inProgress, recentlyCompleted };
}

export function visibleOpenCount(operationalSections) {
  const s = operationalSections || {};
  return (
    (s.needsActionNow?.length || 0) +
    (s.waitingOnOthers?.length || 0) +
    (s.inProgress?.length || 0)
  );
}

/**
 * False-calm disclosure when visible Today is empty but operational debt exists elsewhere.
 */
export function buildFalseEmptyStateDisclosure({
  visibleOpenCount: openCount,
  bucketContinuation,
  commandCenterUrgentCount,
  commandCenterPrimaryCount,
  propertyFilter,
}) {
  const overflow = bucketContinuation
    ? Object.values(bucketContinuation).reduce((sum, n) => sum + Number(n || 0), 0)
    : 0;
  const ccDebt = Math.max(Number(commandCenterUrgentCount || 0), Number(commandCenterPrimaryCount || 0));

  if (openCount === 0 && (overflow > 0 || ccDebt > 0)) {
    const n = overflow > 0 ? overflow : ccDebt;
    return {
      isFalseCalm: true,
      message: `${n} additional operational item${n !== 1 ? 's are' : ' is'} prioritised in Command Centre${propertyFilter ? ' for this property filter' : ''}.`,
      commandCenterPath: '/command-center',
    };
  }

  if (openCount === 0 && overflow === 0 && ccDebt === 0) {
    return {
      isFalseCalm: false,
      genuinelyEmpty: true,
      message:
        'No open operational items in this view. Items appear here when requirements, jobs, or approvals need your action.',
    };
  }

  return {
    isFalseCalm: false,
    genuinelyEmpty: false,
    continuationOverflow: overflow > 0 ? overflow : null,
  };
}
