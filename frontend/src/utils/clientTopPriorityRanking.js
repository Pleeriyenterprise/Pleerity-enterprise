/**
 * Shared ranking for "top priority" tasks — matches Today inbox ordering
 * (`ClientTasksPage`) using unified task fields only.
 */

/**
 * @param {Record<string, unknown>} task
 * @returns {Record<string, unknown>}
 */
export function normalizeTaskForTopPriorityRanking(task) {
  if (!task || typeof task !== 'object') return {};
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  return {
    ...task,
    metadata: meta,
    filter_tags: Array.isArray(task.filter_tags) ? task.filter_tags : [],
    overdue_days: task.overdue_days ?? null,
    urgency: task.urgency || task.urgency_level,
    impact_score: task.impact_score,
    source_type: task.source_type,
    primary_action_type: task.primary_action_type || task.action_type,
  };
}

/**
 * Rank for “Top priority — act now”: overdue compliance → missing evidence → risk signals → rest.
 */
export function topPriorityRank(task) {
  const meta = task.metadata || {};
  const at = String(meta.action_type || '');
  const tags = Array.isArray(task.filter_tags) ? task.filter_tags : [];
  const odDays = Number(task.overdue_days || 0);
  const isCompliance = task.source_type === 'requirement' || tags.includes('compliance');
  const urgentBand = String(task.urgency || task.urgency_level || '').toLowerCase();

  let tier = 3;
  if (at === 'overdue_compliance' || (isCompliance && (odDays > 0 || urgentBand === 'overdue'))) {
    tier = 0;
  } else if (at === 'missing_document' || (isCompliance && task.primary_action_type === 'upload_evidence')) {
    tier = 1;
  } else if (task.source_type === 'risk_signal') {
    tier = 2;
  }

  const sev = String(meta.severity || task.urgency_level || '').toLowerCase();
  const sevOrder = sev === 'critical' ? 0 : sev === 'high' ? 1 : sev === 'medium' ? 2 : 3;

  return {
    tier,
    od: -odDays,
    sevOrder,
    impact: -Number(task.impact_score || 0),
  };
}

export function compareTopPriority(a, b) {
  const ra = topPriorityRank(a);
  const rb = topPriorityRank(b);
  if (ra.tier !== rb.tier) return ra.tier - rb.tier;
  if (ra.tier === 0 && ra.od !== rb.od) return ra.od - rb.od;
  if (ra.sevOrder !== rb.sevOrder) return ra.sevOrder - rb.sevOrder;
  return ra.impact - rb.impact;
}
