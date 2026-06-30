/**
 * Today presentation authority — single source for banner, counters, lanes, and disclosures.
 *
 * Semantic decision (TODAY-PRESENTATION-AUTHORITY-ALIGNMENT-01):
 *   OPERATIONAL_NEEDS_ACTION (Option A)
 *   Banner and KPI "Needs action" count/list share the same operational bucket authority.
 *   Server priority-engine urgent lane (`summary.habit.urgent_open_total`) is disclosed separately
 *   when it exceeds visible operational needs-action rows (list caps / continuation).
 *
 * Does not alter RAOD requirement authority, PAA lifecycle copy, or compliance risk semantics.
 */
import { compareTopPriority } from './clientTopPriorityRanking';
import { buildRequirementShapedRowFromPriorityTask } from './taskRequirementRowAdapter';
import {
  inboxTaskLinkedRequirementId,
  isTaskAssuranceOnly,
} from './portalRequirementAttention';
import {
  isRequirementPendingReviewAttention,
  isRequirementUrgentActionAttention,
  resolveClientRequirementLifecycle,
} from './clientRequirementLifecycle';
import { getOperationalCognition, heroPrimaryFromCognition } from './operationalCognition';
import { getPropertyDisplayName } from './propertyDisplayName';

/** @typedef {'needs_action_now'|'waiting_on_others'|'in_progress'|'recently_completed'|'snoozed'} OperationalBucket */

export const TODAY_PRESENTATION_SEMANTIC_DECISION = 'OPERATIONAL_NEEDS_ACTION';

export const TODAY_PRESENTATION_SEMANTICS = {
  decision: TODAY_PRESENTATION_SEMANTIC_DECISION,
  priorityLane:
    'Server priority-engine section (urgent/upcoming/in_progress). Used for sorting and continuation only.',
  operationalBucket:
    'Client execution bucket (needs action, waiting, in progress). Drives banner, counters, and lane lists.',
  bannerCountSource: 'operational_needs_action_count',
  bannerCopyIntent: 'Items needing your action now — same count as Needs action KPI and list.',
  workOrderRule:
    'Urgent/upcoming work orders needing landlord action → needs_action_now. Contractor-wait states → waiting_on_others. Server in_progress lane → in_progress.',
};

/**
 * @param {Array<unknown>} propertyOptions
 */
export function buildPropertyByIdMap(propertyOptions) {
  const m = new Map();
  if (!Array.isArray(propertyOptions)) return m;
  for (const p of propertyOptions) {
    if (p?.property_id != null) m.set(String(p.property_id), p);
  }
  return m;
}

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

export function pickPrimaryExecutionTask(tasks, requirementsById, propertyById) {
  if (!Array.isArray(tasks) || !tasks.length) return null;
  const sorted = [...tasks]
    .filter((t) => !isTaskAssuranceOnly(t, requirementsById))
    .sort(compareTopPriority);
  if (!sorted.length) return null;
  for (const t of sorted) {
    if (!t?.id) continue;
    const enriched = enrichTaskForExecution(t, requirementsById, propertyById);
    const cog = getOperationalCognition(enriched);
    if (cog && heroPrimaryFromCognition(cog)) return enriched;
    const ta = enriched?.take_action?.primary || enriched?.metadata?.take_action?.primary;
    if (ta?.label) return enriched;
    if (String(t.source_type || '').toLowerCase() === 'work_order') return enriched;
  }
  return enrichTaskForExecution(sorted[0], requirementsById, propertyById);
}

/**
 * Global operational bucket classifier for Today lanes.
 * @returns {OperationalBucket}
 */
export function classifyTaskOperationalBucket(task, requirementsById) {
  if (!task) return 'needs_action_now';
  if (isTaskAssuranceOnly(task, requirementsById)) return 'waiting_on_others';
  const src = String(task.source_type || '').toLowerCase();
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const rid = inboxTaskLinkedRequirementId(task);
  const req = rid && requirementsById instanceof Map ? requirementsById.get(String(rid)) : null;
  const section = String(task.section || '').toLowerCase();
  const woStatus = String(meta.work_order_status || meta.status || '').toUpperCase();

  if (req && isRequirementPendingReviewAttention(req)) return 'waiting_on_others';
  if (src === 'approval' || String(task.primary_action_type || '').toLowerCase() === 'review_approval') {
    return 'waiting_on_others';
  }
  if (src === 'work_order' && ['ASSIGNED', 'SCHEDULED', 'AWAITING_VISIT'].includes(woStatus)) {
    return 'waiting_on_others';
  }
  if (meta.operational_continuation?.has_active_lineage) return 'in_progress';

  if (section === 'recently_completed') return 'recently_completed';
  if (section === 'snoozed') return 'snoozed';
  if (section === 'in_progress') return 'in_progress';

  if (src === 'work_order') {
    return 'needs_action_now';
  }

  if (
    req &&
    !isRequirementUrgentActionAttention(req) &&
    resolveClientRequirementLifecycle(req).state === 'SATISFIED_UNVERIFIED'
  ) {
    return 'waiting_on_others';
  }

  return 'needs_action_now';
}

export function buildOperationalSections(sections, applyFilter, requirementsById) {
  const needsActionNow = [];
  const waitingOnOthers = [];
  const inProgress = [];
  const recentlyCompleted = [];
  const seen = new Set();

  const push = (task, sectionKey) => {
    if (!task?.id || seen.has(task.id)) return;
    seen.add(task.id);
    const classified = classifyTaskOperationalBucket({ ...task, section: sectionKey }, requirementsById);
    const tagged = { ...task, section: sectionKey, _operational_bucket: classified };
    if (classified === 'waiting_on_others') waitingOnOthers.push(tagged);
    else if (classified === 'in_progress') inProgress.push(tagged);
    else if (classified === 'recently_completed') recentlyCompleted.push(tagged);
    else needsActionNow.push(tagged);
  };

  for (const t of applyFilter(sections.urgent || [])) push(t, 'urgent');
  for (const t of applyFilter(sections.upcoming || [])) push(t, 'upcoming');
  for (const t of applyFilter(sections.in_progress || [])) push(t, 'in_progress');
  for (const t of applyFilter(sections.recently_completed || [])) push(t, 'recently_completed');

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

/**
 * @param {Record<string, number>|null|undefined} bucketContinuation
 */
export function buildListCapDisclosure(bucketContinuation) {
  if (!bucketContinuation || typeof bucketContinuation !== 'object') {
    return { show: false, totalHidden: 0, lines: [] };
  }
  const lines = [];
  let totalHidden = 0;
  const labels = {
    urgent: 'priority items needing action',
    upcoming: 'upcoming items',
    in_progress: 'in-progress items',
    recently_completed: 'recently completed items',
    snoozed: 'snoozed items',
  };
  for (const [key, n] of Object.entries(bucketContinuation)) {
    const count = Number(n || 0);
    if (count <= 0) continue;
    totalHidden += count;
    const label = labels[key] || key.replace(/_/g, ' ');
    lines.push(`${count} more ${label} exist beyond this list`);
  }
  return {
    show: totalHidden > 0,
    totalHidden,
    lines,
    summary:
      totalHidden > 0
        ? `${totalHidden} more item${totalHidden !== 1 ? 's' : ''} exist beyond this list — open Command Centre for the full queue.`
        : null,
  };
}

/**
 * Banner copy for operational needs-action count (Option A).
 * @param {number} count
 */
export function formatNeedsActionBannerLine(count) {
  const n = Math.max(0, Number(count) || 0);
  if (n === 0) return null;
  return {
    count: n,
    text: `You have ${n} item${n !== 1 ? 's' : ''} needing action now.`,
  };
}

/**
 * Single Today presentation model — banner, counters, lanes, disclosures.
 */
export function buildTodayPresentationModel({
  payload,
  sections,
  applyFilter,
  requirementsById,
  propertyById,
  commandCenterDepth = null,
  propertyFilter = '',
  categoryFilter = 'all',
}) {
  const summary = payload?.summary || {};
  const habit = summary.habit || {};
  const operational = buildOperationalSections(sections, applyFilter, requirementsById);

  const primaryExecutionTask = pickPrimaryExecutionTask(
    operational.needsActionNow,
    requirementsById,
    propertyById,
  );
  const primaryExecutionId = primaryExecutionTask?.id;
  const needsActionNow = operational.needsActionNow.filter((t) => t.id !== primaryExecutionId);
  const needsActionCount = needsActionNow.length + (primaryExecutionTask ? 1 : 0);

  const snoozed = applyFilter(sections.snoozed || []);
  const recentlyCompleted = applyFilter(sections.recently_completed || []);

  const priorityEngineUrgentCount = Number(summary.urgent_count ?? habit.urgent_open_total ?? 0);
  const listCap = buildListCapDisclosure(payload?.bucket_continuation);

  const urgentPriorityIds = new Set((sections.urgent || []).map((t) => t.id).filter(Boolean));
  const urgentInProgressVisible = operational.inProgress.filter((t) => urgentPriorityIds.has(t.id));

  const falseEmptyDisclosure = buildFalseEmptyStateDisclosure({
    visibleOpenCount: visibleOpenCount(operational),
    bucketContinuation: payload?.bucket_continuation,
    commandCenterUrgentCount: commandCenterDepth?.urgent,
    commandCenterPrimaryCount: commandCenterDepth?.primary,
    propertyFilter,
  });

  const needsActionBanner = formatNeedsActionBannerLine(needsActionCount);
  const showHabitBanner =
    needsActionCount > 0 ||
    Number(habit.items_due_or_expiring_in_7_days || 0) > 0 ||
    Number(habit.tasks_acknowledged_last_7_days || 0) > 0;

  const priorityUrgentBeyondNeedsAction = Math.max(0, priorityEngineUrgentCount - needsActionCount);

  return {
    semanticDecision: TODAY_PRESENTATION_SEMANTIC_DECISION,
    banner: {
      show: showHabitBanner,
      needsAction: needsActionBanner,
      dueInSevenDays: Number(habit.items_due_or_expiring_in_7_days || 0),
      acknowledgedLastSevenDays: Number(habit.tasks_acknowledged_last_7_days || 0),
    },
    counters: {
      needsAction: needsActionCount,
      waiting: operational.waitingOnOthers.length,
      inProgress: operational.inProgress.length,
      snoozed: snoozed.length,
    },
    lanes: {
      primaryExecutionTask,
      needsActionNow,
      waitingOnOthers: operational.waitingOnOthers,
      inProgress: operational.inProgress,
      recentlyCompleted,
      snoozed,
      hidden: sections.hidden || [],
    },
    priorityEngine: {
      urgentLaneCount: priorityEngineUrgentCount,
      urgentBeyondOperationalNeedsAction: priorityUrgentBeyondNeedsAction,
    },
    listCap,
    inProgressDisclosure: {
      urgentPriorityCount: urgentInProgressVisible.length,
      hint:
        urgentInProgressVisible.length > 0
          ? `Includes ${urgentInProgressVisible.length} priority urgent item${urgentInProgressVisible.length !== 1 ? 's' : ''} tracked as in progress.`
          : operational.inProgress.length > 0
            ? null
            : 'No active jobs or workflows in progress.',
    },
    falseEmptyDisclosure,
    filters: {
      categoryFilter,
      propertyFilter: propertyFilter || null,
      countsMatchFilteredLists: true,
    },
    isSemanticallyConsistent:
      needsActionCount === operational.needsActionNow.length &&
      (needsActionBanner === null || needsActionBanner.count === needsActionCount),
  };
}

export { isTaskAssuranceOnly } from './portalRequirementAttention';
