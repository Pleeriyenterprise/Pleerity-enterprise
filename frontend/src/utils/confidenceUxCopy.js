/**
 * Confidence UX — pre-action clarity and post-action feedback copy (messaging only).
 * Keep strings concrete: what changed + why it matters; avoid generic “success” / “completed”.
 */

/** Page-level: one sentence under title (Today). */
export const TODAY_PAGE_CONFIDENCE_LINE =
  'Primary actions update your portfolio record—requirements, jobs, and approvals.';

/** Command Center intro reinforcement. */
export const COMMAND_CENTER_CONFIDENCE_LINE =
  'Counts here reflect compliance and jobs across the portfolio—they refresh when you return after acting elsewhere.';

/** Jobs list — why the list matters. */
export const JOBS_PAGE_CONFIDENCE_LINE =
  'Moving jobs forward updates SLA and compliance execution so each property’s record matches reality.';

/** Requirements hub — outcome-focused. */
export const REQUIREMENTS_PAGE_CONFIDENCE_LINE =
  'Uploads, dates, and applicability here directly affect overdue counts and how each property scores.';

/** Job detail — why lifecycle actions matter. */
export const JOB_DETAIL_CONFIDENCE_LINE =
  'Each step updates this job’s record so SLA timers and compliance proof can match what happened on the property.';

/**
 * Whether to show the per-card confidence line on Today (reduce noise on pure navigation / low-signal tasks).
 * @param {Record<string, unknown>|null|undefined} task
 */
export function shouldShowTodayTaskConfidence(task) {
  if (!task || typeof task !== 'object') return false;

  const u = String(task.urgency || '').toLowerCase();
  const ul = String(task.urgency_level || '').toLowerCase();
  if (u === 'overdue' || ul === 'overdue') return true;

  const canonical = todayTaskCanonicalActionTypesForConfidence(task);
  if (canonical.has('upload_document') || canonical.has('approve_quote') || canonical.has('assign_contractor')) {
    return true;
  }

  return taskHasComplianceImpactForConfidence(task);
}

/** Maps unified-task fields to display-rule action buckets. */
function todayTaskCanonicalActionTypesForConfidence(task) {
  const types = new Set();
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const at = String(meta.action_type || '');
  const pat = String(task.primary_action_type || task.action_context_type || '');
  const st = String(task.source_type || '');

  if (at === 'missing_document' || pat === 'upload_evidence') types.add('upload_document');

  const ba = Array.isArray(task.business_actions) ? task.business_actions : [];
  for (const a of ba) {
    const aid = String(a.id || '').toLowerCase();
    const nav = String(a.navigate || '').toLowerCase();
    if (aid === 'upload_certificate' || (aid === 'take_action_primary' && nav.includes('/documents'))) {
      types.add('upload_document');
    }
  }

  if (
    at === 'pending_invoice_approval' ||
    (st === 'approval' && pat === 'review_approval') ||
    (meta.domain === 'billing' && String(meta.billing_milestone_type || '').includes('invoice'))
  ) {
    types.add('approve_quote');
  }
  for (const a of ba) {
    if (String(a.id || '').toLowerCase() === 'view_approval') types.add('approve_quote');
  }

  const booking = String(meta.compliance_booking_status || task.compliance_booking_status || '').toUpperCase();
  if (st === 'work_order' && at === 'open_work_order') {
    const hay = `${String(task.title || '')} ${String(task.description || '')}`.toLowerCase();
    if (/assign|unassigned|contractor/.test(hay) || booking === 'AWAITING_CONTRACTOR_RESPONSE') {
      types.add('assign_contractor');
    }
  }

  return types;
}

function taskHasComplianceImpactForConfidence(task) {
  const il = String(task.impact_label || '').trim();
  if (il) return true;
  const score = Number(task.impact_score);
  if (!Number.isNaN(score) && score >= 55) return true;
  return false;
}

/**
 * Surfaces whether the inbox row came from tenant activity vs automated portfolio signals (existing fields only).
 * @param {Record<string, unknown>|null|undefined} task
 * @returns {string|null}
 */
export function todayTaskSourceAttributionLine(task) {
  if (!task || typeof task !== 'object') return null;
  const st = String(task.source_type || '').toLowerCase();
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  if (st === 'tenant_request') return 'Requested by tenant';
  if (meta.created_by_tenant === true || meta.tenant_initiated === true) return 'Requested by tenant';
  if (st === 'approval') return null;
  if (st === 'requirement' || st === 'work_order' || st === 'risk_signal' || st === 'issue') {
    return 'Flagged for review';
  }
  return null;
}

/**
 * Short line above Today task CTAs (per task shape / metadata).
 * @param {Record<string, unknown>|null|undefined} task
 * @returns {string|null}
 */
export function todayTaskConfidenceLine(task) {
  if (!task || typeof task !== 'object') return null;
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const at = String(meta.action_type || '');
  const st = String(task.source_type || '');
  const pat = String(task.primary_action_type || task.action_context_type || '');

  if (at === 'missing_document' || pat === 'upload_evidence') {
    return 'This document is required to keep this property compliant.';
  }
  if (at === 'overdue_compliance' || (st === 'requirement' && Number(task.overdue_days) > 0)) {
    return 'This requirement is overdue and affects compliance status.';
  }
  if (at === 'certificate_expiring_soon') {
    return 'Acting before expiry keeps this property inside compliance windows.';
  }
  if (at === 'work_order_sla_breached' || at === 'work_order_near_sla_breach') {
    return 'This job is blocking progress on this property until the deadline risk is cleared.';
  }
  if (at === 'open_work_order' || st === 'work_order') {
    return 'This job is blocking progress on this property until the next step is completed.';
  }
  if (at === 'risk_signal' || st === 'risk_signal') {
    return 'Decide what to do next.';
  }
  if (at === 'open_operational_issue' || st === 'issue') {
    return 'This issue has not been reviewed yet and may affect maintenance priority.';
  }
  if (at === 'pending_invoice_approval' || st === 'approval') {
    return 'Your approval records the decision and allows contractor payment to proceed when rules allow.';
  }
  if (st === 'tenant_request') {
    return 'Responding links tenant evidence to the right requirement so compliance stays traceable.';
  }

  const urg = String(task.urgency || task.urgency_level || '').toLowerCase();
  if (urg === 'overdue') {
    return 'This item is overdue—acting now limits compliance drift for this property.';
  }
  if (taskHasComplianceImpactForConfidence(task)) {
    return 'This item advances portfolio records for this property.';
  }
  return null;
}

/**
 * One short positive reinforcement line when an action measurably improves compliance posture.
 * Max one line; skip idempotent replays and weak signals (do not overuse).
 *
 * @param {Record<string, unknown>|null|undefined} outcome
 * @returns {string|null}
 */
export function positiveReinforcementLine(outcome) {
  if (!outcome || typeof outcome !== 'object') return null;
  if (outcome.idempotent === true) return null;

  const overdueN = Number(outcome.overdue_requirements_resolved);
  if (!Number.isNaN(overdueN) && overdueN > 0) {
    return overdueN === 1 ? '1 overdue requirement resolved' : `${overdueN} overdue requirements resolved`;
  }

  const riskReduced =
    String(outcome.risk_change || '').toLowerCase() === 'reduced' ||
    outcome.compliance_risk_reduced === true ||
    String(outcome.compliance_impact || '').toLowerCase() === 'improved';
  if (riskReduced) return 'Compliance risk reduced';

  const standingUp =
    outcome.portfolio_status_improving === true || String(outcome.status_change || '').toLowerCase() === 'improved';
  if (standingUp) return 'Fewer urgent items now';

  return null;
}

/**
 * Title + description for the Reports nudge after compliance-outcome (ties copy to what just happened).
 * @param {Record<string, unknown>|null|undefined} detail
 * @returns {{ title: string, description: string }}
 */
export function complianceReportNudgeToastCopy(detail) {
  if (!detail || typeof detail !== 'object') {
    return {
      title: 'Keep a compliance record',
      description:
        'Download a compliance report from Reports when you need to archive or share your regulatory position.',
    };
  }
  if (detail.job_execution_milestone === true) {
    return {
      title: 'Compliance progress recorded',
      description:
        'Download a compliance report to keep a record of this job update and your execution trail.',
    };
  }
  if (detail.report_hint_eligible === true) {
    return {
      title: 'Compliance evidence updated',
      description:
        'Download a compliance report to keep a record of this document update and your portfolio position.',
    };
  }
  const reinf = positiveReinforcementLine(detail);
  if (reinf) {
    return {
      title: 'Compliance position updated',
      description: `${reinf} — download a compliance report from Reports to capture this compliance update.`,
    };
  }
  return {
    title: 'Keep a compliance record',
    description: 'Download a compliance report to keep a record of this portfolio compliance update.',
  };
}

/**
 * Minimum gap between compliance-report nudge toasts (session-wide, client portal).
 * 2m reduces back-to-back prompts after clustered uploads/actions; raise further if it still feels noisy in production.
 */
export const COMPLIANCE_REPORT_HINT_COOLDOWN_MS = 120000;

/** Whether to nudge Reports after a meaningful compliance win (frontend event detail only). */
export function shouldSuggestComplianceReportHint(detail) {
  if (!detail || typeof detail !== 'object') return false;
  if (detail.report_hint_eligible === true) return true;
  if (detail.job_execution_milestone === true) return true;
  if (positiveReinforcementLine(detail)) return true;
  return false;
}

/**
 * Sonner options: add `description` only when reinforcement applies (single line).
 * @param {Record<string, unknown>|null|undefined} outcome
 * @returns {{ description?: string }}
 */
export function reinforcementToastOptions(outcome) {
  const description = positiveReinforcementLine(outcome);
  return description ? { description } : {};
}

/**
 * Single toast description: portfolio reinforcement when present, else one concrete fallback (never generic “Success”).
 * @param {Record<string, unknown>|null|undefined} outcome
 * @param {{ fallbackDescription?: string }} [opts]
 * @returns {{ description?: string }}
 */
export function complianceActionToastOptions(outcome, opts = {}) {
  const reinf = positiveReinforcementLine(outcome);
  if (reinf) return { description: reinf };
  if (outcome && typeof outcome === 'object' && outcome.idempotent === true) return {};
  const fb = opts.fallbackDescription && String(opts.fallbackDescription).trim();
  if (fb) return { description: fb };
  return {};
}

/** Meaningful default after job lifecycle API success (action id from ClientJobDetailPage). */
export function jobLifecycleSuccessMessage(actionId) {
  const id = String(actionId || '');
  const map = {
    request_booking: 'Visit request sent. Progress is recorded—await the contractor response to unblock scheduling.',
    propose_schedule: 'Proposed time saved. Progress is recorded—confirmation moves the job forward on this property.',
    reschedule_booking: 'Reschedule proposed. Progress is recorded—confirmation updates the agreed visit time.',
    confirm_visit: 'Visit confirmed. Progress is recorded—the job can proceed on the scheduled date.',
    cancel_booking: 'Booking cancelled. Progress is recorded—you can propose a new time when ready.',
    mark_no_access: 'No-access note saved. Progress is recorded—reschedule when access is available.',
    mark_reschedule_required: 'Reschedule flagged. Progress is recorded—pick a new time to keep the job moving.',
    start: 'Job marked in progress. Progress is recorded—completion proof can follow for compliance jobs.',
    awaiting_parts: 'Awaiting parts recorded. Progress is recorded—SLA clocks can reflect the hold.',
    complete: 'Job completed — one less risk to manage on this property.',
    verify: 'Verification recorded — compliance evidence is stronger and the record can close.',
    close_job: 'Job closed — this property’s execution queue is slimmer.',
    cancel: 'Job cancelled. Progress is recorded—this property is no longer blocked by this job.',
    resume_after_parts: 'Job resumed. Progress is recorded—work can continue toward completion.',
    clear_operational_exception: 'Hold cleared. Progress is recorded—the job can move again without the block.',
    approve_quote: 'Quote approved. Progress is recorded—work can proceed at the agreed price.',
    link_document: 'Document linked. Progress is recorded—proof is attached for review.',
    attach_completion_proof: 'Completion proof attached. Progress is recorded—verification can proceed.',
    assign: 'Contractor assigned. Progress is recorded—they can accept and respond to booking requests.',
    create_contractor_assign: 'Contractor saved and assigned. Progress is recorded—use scheduling to request the visit.',
    op_ex: 'Operational note saved. Progress is recorded—parties see why the job is paused.',
  };
  return map[id] || 'Update saved. Progress is recorded on this job for this property.';
}
