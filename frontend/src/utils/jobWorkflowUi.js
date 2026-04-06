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
