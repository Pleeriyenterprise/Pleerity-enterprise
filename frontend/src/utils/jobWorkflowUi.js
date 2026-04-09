/**
 * Shared job lifecycle presentation for client / admin surfaces.
 * Canonical status rules mirror backend `derive_canonical_job_status` (compliance_workflow_service).
 */

const KIND_MAINTENANCE = 'MAINTENANCE';
const KIND_COMPLIANCE = 'COMPLIANCE';

/** @param {Record<string, unknown>|null|undefined} wo */
export function deriveCanonicalJobStatus(wo) {
  const st = String(wo?.status || '')
    .trim()
    .toUpperCase();
  const kind = String(wo?.work_order_kind || KIND_MAINTENANCE)
    .trim()
    .toUpperCase() || KIND_MAINTENANCE;
  if (st === 'CANCELLED') return 'CANCELLED';
  if (st === 'VERIFIED') return 'VERIFIED';
  if (st === 'CLOSED') return 'CLOSED';
  if (st === 'COMPLETED') return 'COMPLETED';
  if (kind === KIND_MAINTENANCE && st === 'DRAFT') return 'DRAFT';
  if (kind === KIND_MAINTENANCE && st === 'AWAITING_PARTS') return 'AWAITING_PARTS';
  if (kind === KIND_MAINTENANCE && st === 'SCHEDULED') return 'SCHEDULED';
  const oe = String(wo?.operational_exception || '')
    .trim()
    .toUpperCase();
  if (oe === 'NO_ACCESS') return 'NO_ACCESS';
  if (oe === 'RESCHEDULE_REQUIRED') return 'RESCHEDULE_REQUIRED';
  if (oe === 'FOLLOW_UP_REQUIRED') return 'FOLLOW_UP_REQUIRED';
  if (st === 'IN_PROGRESS') return 'IN_PROGRESS';
  const sched = String(wo?.schedule_status || '')
    .trim()
    .toLowerCase();
  if (kind === KIND_COMPLIANCE) {
    if (sched === 'confirmed') return 'BOOKED';
    if (sched === 'proposed' && String(wo?.scheduled_at || '').trim()) return 'BOOKING_REQUESTED';
  }
  if (String(wo?.contractor_id || '').trim()) return 'ASSIGNED';
  return 'OPEN';
}

const CLIENT_PROGRESS_STEPS = [
  'Job created',
  'Contractor assigned',
  'Visit booked',
  'Work completed',
  'Proof reviewed',
  'Closed',
];

/** Client oversight tracker (aligned with product copy, not contractor execution steps). */
export function clientJobProgressFromJob(job) {
  const steps = CLIENT_PROGRESS_STEPS;
  const st = String(job?.status || '').toUpperCase();
  if (st === 'CANCELLED') return { steps, currentIndex: -1, completedFlags: [] };

  const hasContractor = !!String(job?.contractor_id || '').trim();
  const sched = String(job?.schedule_status || '').toLowerCase();
  const hasBookedVisit = sched === 'confirmed' && !!String(job?.scheduled_at || '').trim();
  const workDone = ['COMPLETED', 'VERIFIED', 'CLOSED'].includes(st);
  const proofReviewed = st === 'VERIFIED' || st === 'CLOSED';
  const fullyClosed = st === 'CLOSED';

  const completedFlags = [true, hasContractor, hasBookedVisit, workDone, proofReviewed, fullyClosed];
  let currentIndex = completedFlags.findIndex((f) => !f);
  if (currentIndex === -1) currentIndex = steps.length - 1;

  return { steps, currentIndex, completedFlags };
}

const CANONICAL_LABELS = {
  OPEN: 'Waiting for a contractor',
  ASSIGNED: 'Contractor assigned — booking next',
  BOOKING_REQUESTED: 'Visit time proposed — confirmation pending',
  BOOKED: 'Visit booked — work not yet marked complete',
  SCHEDULED: 'Visit scheduled',
  IN_PROGRESS: 'Work in progress',
  AWAITING_PARTS: 'Awaiting parts',
  COMPLETED: 'Work marked complete — review proof and close out',
  VERIFIED: 'Verified — final close-out may remain',
  CLOSED: 'Job closed',
  CANCELLED: 'Job cancelled',
  NO_ACCESS: 'On hold: no access',
  RESCHEDULE_REQUIRED: 'On hold: reschedule required',
  FOLLOW_UP_REQUIRED: 'On hold: follow-up required',
  DRAFT: 'Draft — finish setup',
};

/**
 * Oversight-oriented copy for the client "Current update" block (not a full next_actions dump).
 * @param {Record<string, unknown>|null|undefined} job
 */
export function clientCurrentUpdateSummary(job) {
  const canonical = String(job?.job_status || '').trim() || deriveCanonicalJobStatus(job);
  const headline = CANONICAL_LABELS[canonical] || canonical.replace(/_/g, ' ');
  const ss = String(job?.schedule_status || '').toLowerCase();
  const when = job?.scheduled_at ? formatShortWhen(job.scheduled_at) : null;
  const lines = [];
  if (when && ss === 'confirmed') lines.push(`Confirmed visit: ${when}.`);
  else if (when && ss === 'proposed') lines.push(`Proposed visit: ${when} — confirm when agreed.`);
  if (job?.operational_exception && canonical !== 'NO_ACCESS' && canonical !== 'RESCHEDULE_REQUIRED') {
    lines.push(`Operational note: ${String(job.operational_exception).replace(/_/g, ' ')}.`);
  }
  return { headline, lines, canonical };
}

function formatShortWhen(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return String(iso);
  }
}

/** Primary hero CTA for client oversight — only when a visit decision is pending (spec: no execution-console hero). */
export function clientHeroOversightAction(nextActions) {
  const na = (nextActions || []).filter((a) => a?.id && a.id !== 'none');
  if (na.some((a) => a.id === 'confirm_visit')) {
    return {
      kind: 'scroll',
      scrollId: 'client-job-visit',
      label: 'Review proposed visit',
    };
  }
  return null;
}

export function adminInterventionRequired(canonical, operationalException) {
  const c = String(canonical || '').toUpperCase();
  if (['NO_ACCESS', 'RESCHEDULE_REQUIRED', 'FOLLOW_UP_REQUIRED'].includes(c)) return true;
  return !!String(operationalException || '').trim();
}

const ADMIN_PROGRESS_STEPS = ['Created', 'Assigned', 'Booked / scheduled', 'In progress', 'Complete', 'Verified / closed'];

/** Admin: simplified strip plus caller shows raw `status` / `job_status` beside it. */
export function adminSimplifiedProgressFromWorkOrder(wo) {
  const steps = ADMIN_PROGRESS_STEPS;
  const st = String(wo?.status || '').toUpperCase();
  const js = String(wo?.job_status || deriveCanonicalJobStatus(wo)).toUpperCase();
  if (st === 'CANCELLED') return { steps, currentIndex: -1 };
  if (st === 'CLOSED' || st === 'VERIFIED') return { steps, currentIndex: 5 };
  if (st === 'COMPLETED') return { steps, currentIndex: 4 };
  if (st === 'IN_PROGRESS' || st === 'AWAITING_PARTS' || js === 'IN_PROGRESS' || js === 'AWAITING_PARTS') {
    return { steps, currentIndex: 3 };
  }
  const schedOk = String(wo?.schedule_status || '').toLowerCase() === 'confirmed' && !!String(wo?.scheduled_at || '').trim();
  if (schedOk || js === 'BOOKED' || js === 'BOOKING_REQUESTED' || st === 'SCHEDULED') {
    return { steps, currentIndex: 2 };
  }
  if (String(wo?.contractor_id || '').trim() || st === 'ASSIGNED' || js === 'ASSIGNED') {
    return { steps, currentIndex: 1 };
  }
  return { steps, currentIndex: 0 };
}

/**
 * Priority order for which `next_actions` item to highlight in client UI.
 * Aligns with `recoveryLineFromNextActions` in `ClientJobDetailPage` (extended for quotes / billing).
 */
const CLIENT_JOB_NEXT_ACTION_PRIORITY = [
  'clear_operational_exception',
  'resume_after_parts',
  'propose_schedule',
  'request_booking',
  'reschedule_booking',
  'confirm_visit',
  'assign_contractor',
  'approve_quote',
  'reject_quote',
  'link_document',
  'attach_completion_proof',
  'verify',
  'complete',
  'start',
  'awaiting_parts',
  'close_job',
  'set_operational_exception',
  'cancel_booking',
  'mark_no_access',
  'mark_reschedule_required',
  'cancel',
];

/** @param {Record<string, unknown>|null|undefined} job */
export function prioritizedClientJobNextAction(job) {
  const na = (job?.next_actions || []).filter((a) => a?.id && a.id !== 'none');
  if (!na.length) return null;
  for (const id of CLIENT_JOB_NEXT_ACTION_PRIORITY) {
    const found = na.find((x) => x.id === id);
    if (found) return found;
  }
  return na[0];
}

function isTerminalClientJob(job) {
  const st = String(job?.status || '').toUpperCase();
  if (['COMPLETED', 'VERIFIED', 'CLOSED', 'CANCELLED'].includes(st)) return true;
  const js = String(job?.job_status || '').toUpperCase();
  if (['CLOSED', 'CANCELLED', 'VERIFIED'].includes(js)) return true;
  return false;
}

/**
 * Single human-readable “next step” for job preview (same labels as full job page `next_actions`).
 * @param {Record<string, unknown>|null|undefined} job — workflow job payload (`GET /jobs/:id`)
 */
export function jobPreviewNextStepLine(job) {
  const a = prioritizedClientJobNextAction(job);
  if (a?.label) return a.hint ? `${a.label} — ${a.hint}` : a.label;
  if (isTerminalClientJob(job)) return 'No action needed right now';
  return 'Review progress on the full job page';
}

/**
 * Natural clause after "Manage job to …" — tuned so the button does not echo raw API labels mechanically.
 * Unknown ids fall back to plain "Manage job" (next-step line still shows the full label).
 */
const MANAGE_JOB_CTA_PHRASE_BY_ACTION_ID = {
  clear_operational_exception: 'clear the hold',
  resume_after_parts: 'resume after parts arrive',
  propose_schedule: 'propose a visit time',
  request_booking: 'request a visit',
  reschedule_booking: 'reschedule the visit',
  confirm_visit: 'confirm the visit',
  assign_contractor: 'assign a contractor',
  approve_quote: 'approve the quote',
  reject_quote: 'respond to the quote',
  link_document: 'link certificate or evidence',
  attach_completion_proof: 'upload completion proof',
  verify: 'verify the work',
  complete: 'mark work complete',
  start: 'start on-site work',
  awaiting_parts: 'mark that parts are needed',
  close_job: 'close the job',
  set_operational_exception: 'put the job on hold',
  cancel_booking: 'cancel the visit',
  mark_no_access: 'record no access',
  mark_reschedule_required: 'mark that a reschedule is needed',
  cancel: 'cancel the job',
};

/**
 * Primary CTA for job preview drawer.
 * @param {Record<string, unknown>|null|undefined} job
 */
export function jobPreviewManageJobCtaLabel(job) {
  const a = prioritizedClientJobNextAction(job);
  if (!a) return 'Manage job';
  const phrase = a.id ? MANAGE_JOB_CTA_PHRASE_BY_ACTION_ID[String(a.id)] : null;
  if (phrase) return `Manage job to ${phrase}`;
  return 'Manage job';
}

/**
 * Fallback when only maintenance work-order shape is available (no `next_actions`).
 * @param {Record<string, unknown>|null|undefined} wo
 */
export function maintenanceWorkOrderPreviewDecision(wo) {
  const st = String(wo?.status || '').toUpperCase();
  if (['COMPLETED', 'VERIFIED', 'CLOSED', 'CANCELLED'].includes(st)) {
    return { nextStep: 'No action needed right now', cta: 'Manage job' };
  }
  if (!(wo?.contractor_id || '').toString().trim()) {
    return { nextStep: 'Assign a contractor', cta: 'Manage job to assign a contractor' };
  }
  return { nextStep: 'Review progress on the full job page', cta: 'Manage job' };
}

/** Client-facing label: compliance-led vs repair/maintenance (aligned with `ClientJobDetailPage`). */
export function workOrderKindClientLabel(wo) {
  const k = String(wo?.work_order_kind || '').toUpperCase();
  if (k === 'COMPLIANCE') return 'Compliance job';
  return 'Repair / maintenance';
}

/** Badge styles so job kind stays visible in dense tables without relying on section grouping alone. */
export function workOrderKindBadgeClassName(wo) {
  const k = String(wo?.work_order_kind || '').toUpperCase();
  return k === 'COMPLIANCE'
    ? 'bg-sky-50 text-sky-900 border-sky-200'
    : 'bg-slate-100 text-slate-800 border-slate-200';
}
