/**
 * Contractor portal: lifecycle stages, prioritisation, next-step copy, and allowed status transitions.
 * Aligns with backend maintenance_service work order statuses and invoice approval flow.
 */
import { progressTrackerFromContract } from './jobWorkflowUi';

const TERMINAL = new Set(['CANCELLED', 'COMPLETED', 'CLOSED', 'VERIFIED']);
const ACTIVE = new Set(['OPEN', 'ASSIGNED', 'SCHEDULED', 'IN_PROGRESS', 'AWAITING_PARTS']);

const STATUS_LABELS = {
  SCHEDULED: 'Scheduled',
  IN_PROGRESS: 'In progress',
  AWAITING_PARTS: 'Awaiting parts',
  COMPLETED: 'Completed',
};

export function parseIsoDate(s) {
  if (!s) return null;
  try {
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}

export function formatMoneyGbp(n) {
  if (n == null || n === '' || Number.isNaN(Number(n))) return null;
  const v = Number(n);
  return `£${v.toFixed(2)}`;
}

/** Pre-fill invoice amount from job estimate (max, else min). */
export function defaultInvoiceAmountFieldFromWorkOrder(wo) {
  const mx = wo?.cost_estimate_max != null ? Number(wo.cost_estimate_max) : null;
  const mn = wo?.cost_estimate_min != null ? Number(wo.cost_estimate_min) : null;
  if (mx != null && !Number.isNaN(mx)) return String(mx);
  if (mn != null && !Number.isNaN(mn)) return String(mn);
  return '';
}

/** Map API contractor_invoice_state / raw status to short UI copy. */
export function formatContractorInvoiceStateLabel(inv) {
  const mapped = (inv?.contractor_invoice_state || '').toUpperCase();
  const raw = (inv?.status || '').toLowerCase();
  if (mapped === 'PAID' || raw === 'paid') {
    return inv?.paid_at
      ? `Paid on ${new Date(inv.paid_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}`
      : 'Paid';
  }
  const labels = {
    SUBMITTED: 'Waiting for approval',
    UNDER_REVIEW: 'Correction requested',
    APPROVED: 'Approved',
    REJECTED: 'Rejected',
  };
  if (labels[mapped]) return labels[mapped];
  if (raw === 'pending') return 'Waiting for approval';
  if (raw === 'needs_info') return 'Correction requested';
  if (raw === 'approved') return 'Approved';
  if (raw === 'rejected') return 'Rejected';
  return inv?.status || '—';
}

export function getJobValueDisplay(wo) {
  const mn = wo?.cost_estimate_min;
  const mx = wo?.cost_estimate_max;
  if (mn != null && mx != null && Number(mn) !== Number(mx)) {
    return `${formatMoneyGbp(mn)} – ${formatMoneyGbp(mx)}`;
  }
  if (mx != null) return formatMoneyGbp(mx);
  if (mn != null) return formatMoneyGbp(mn);
  return '—';
}

export function getJobTypeLabel(wo) {
  const kind = (wo?.work_order_kind || 'MAINTENANCE').toString().toUpperCase();
  if (kind === 'COMPLIANCE') {
    const rc = (wo?.requirement_code || '').replace(/_/g, ' ');
    return rc ? `Compliance — ${rc}` : 'Compliance job';
  }
  const cat = (wo?.category || 'General').toString().replace(/_/g, ' ');
  return `Maintenance — ${cat}`;
}

export function buildInvoiceByWorkOrderId(invoices) {
  const m = {};
  const rank = (inv) => {
    const s = (inv?.status || '').toLowerCase();
    if (s === 'paid') return 5;
    if (s === 'approved') return 4;
    if (s === 'pending') return 3;
    if (s === 'needs_info') return 2;
    if (s === 'rejected') return 1;
    return 0;
  };
  (invoices || []).forEach((inv) => {
    const w = inv?.work_order_id;
    if (!w) return;
    const prev = m[w];
    if (!prev || rank(inv) > rank(prev)) m[w] = inv;
  });
  return m;
}

/** Display lifecycle for badges (not all are mutable contractor statuses). */
export function getLifecycleStage(wo, invoiceByWo) {
  const st = (wo?.status || '').toUpperCase();
  const inv = invoiceByWo?.[wo?.work_order_id];
  const invSt = (inv?.status || '').toLowerCase();

  if (invSt === 'paid') return 'PAID';
  if (inv && ['pending', 'needs_info', 'approved', 'rejected'].includes(invSt)) {
    if (invSt === 'rejected') return 'INVOICED_REJECTED';
    return 'INVOICED';
  }
  if (TERMINAL.has(st) && st !== 'CANCELLED') return 'COMPLETED';
  if (st === 'CANCELLED') return 'CANCELLED';
  if (st === 'IN_PROGRESS' || st === 'AWAITING_PARTS') return 'IN_PROGRESS';
  const ss = (wo?.schedule_status || '').toLowerCase();
  if (ss === 'confirmed' && wo?.scheduled_at) return 'SCHEDULED';
  if (st === 'SCHEDULED') return 'SCHEDULED';
  return 'ASSIGNED';
}

export function getLifecycleBadge(stage) {
  const map = {
    ASSIGNED: { label: 'Action required', tone: 'amber' },
    SCHEDULED: { label: 'Visit scheduled', tone: 'teal' },
    IN_PROGRESS: { label: 'In progress', tone: 'blue' },
    COMPLETED: { label: 'Work complete', tone: 'green' },
    INVOICED: { label: 'Invoice submitted', tone: 'purple' },
    INVOICED_REJECTED: { label: 'Invoice needs attention', tone: 'red' },
    PAID: { label: 'Paid', tone: 'green' },
    CANCELLED: { label: 'Cancelled', tone: 'slate' },
  };
  return map[stage] || { label: stage, tone: 'slate' };
}

export function toneToClasses(tone) {
  const t = {
    red: 'bg-red-50 text-red-900 border-red-200',
    amber: 'bg-amber-50 text-amber-950 border-amber-200',
    green: 'bg-emerald-50 text-emerald-900 border-emerald-200',
    teal: 'bg-teal-50 text-teal-900 border-teal-200',
    blue: 'bg-sky-50 text-sky-900 border-sky-200',
    purple: 'bg-violet-50 text-violet-900 border-violet-200',
    slate: 'bg-slate-100 text-slate-800 border-slate-200',
  };
  return t[tone] || t.slate;
}

export function isSlaOverdue(wo, now = new Date()) {
  const st = (wo?.status || '').toUpperCase();
  if (TERMINAL.has(st)) return false;
  if (!ACTIVE.has(st)) return false;
  const due = parseIsoDate(wo?.sla_complete_by);
  if (!due) return false;
  return due < now;
}

export function isPendingScheduling(wo) {
  const st = (wo?.status || '').toUpperCase();
  if (TERMINAL.has(st)) return false;
  if (!ACTIVE.has(st)) return false;
  const ss = (wo?.schedule_status || '').toLowerCase();
  if (ss === 'confirmed' && wo?.scheduled_at) return false;
  return true;
}

export function isCompletedPipeline(wo) {
  const st = (wo?.status || '').toUpperCase();
  return st === 'COMPLETED' || st === 'VERIFIED' || st === 'CLOSED';
}

export function getBlockOrCancelReason(wo) {
  const st = (wo?.status || '').toUpperCase();
  if (st === 'CANCELLED') {
    return (
      wo?.routing_invalidation_reason ||
      wo?.resolution_outcome ||
      wo?.routing_decline_note ||
      'This job was cancelled.'
    );
  }
  const ss = (wo?.schedule_status || '').toLowerCase();
  if (ss === 'cancelled') {
    return wo?.schedule_notes || wo?.schedule_reschedule_reason || 'Visit was cancelled.';
  }
  return null;
}

export function getNextStepMessage(wo, invoiceByWo) {
  const st = (wo?.status || '').toUpperCase();
  const stage = getLifecycleStage(wo, invoiceByWo);
  const inv = invoiceByWo?.[wo?.work_order_id];
  const invSt = (inv?.status || '').toLowerCase();

  if (st === 'CANCELLED') return 'No further action is required on this job.';

  if (invSt === 'paid') return 'Payment has been recorded. Thank you.';

  if (invSt === 'rejected') {
    return 'Invoice rejected—check your email for the reason. Submit a revised invoice when the client allows it.';
  }
  if (invSt === 'needs_info')
    return 'More detail requested on your invoice—reply through the client thread, then resubmit if needed.';

  if (invSt === 'approved') {
    return 'Invoice approved—payment sits with the client. Follow up if funds are delayed.';
  }

  if (invSt === 'pending') {
    return 'Invoice is with the client for approval. You will be notified when it is decided.';
  }

  if (stage === 'COMPLETED' && !inv) {
    return 'Submit your invoice so the client can approve and record payment.';
  }

  if (st === 'IN_PROGRESS' || st === 'AWAITING_PARTS') {
    const docHint =
      (wo?.work_order_kind || '').toUpperCase() === 'COMPLIANCE' && wo?.expected_output_document_type
        ? ` Upload the ${wo.expected_output_document_type} when work is finished.`
        : ' Upload evidence (photos, certificates) when work is finished.';
    return `Complete the work on site, then mark the job complete.${docHint}`;
  }

  if ((wo?.schedule_status || '').toLowerCase() === 'confirmed' && wo?.scheduled_at) {
    try {
      const d = new Date(wo.scheduled_at);
      const when = d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
      return `Attend the visit on ${when}. Mark in progress on arrival; request a change if you cannot attend.`;
    } catch {
      return 'Attend the scheduled visit. Mark in progress when you arrive.';
    }
  }

  if ((wo?.schedule_status || '').toLowerCase() === 'proposed') {
    const sb = (wo?.scheduled_by || '').toLowerCase();
    if (sb === 'client' || sb === 'admin') {
      return 'Confirm the proposed visit time—propose a different time if needed.';
    }
    return 'Waiting for the client to confirm your proposed visit time.';
  }

  if (st === 'OPEN' || st === 'ASSIGNED') {
    return 'Accept to unlock scheduling and uploads. Decline if you cannot take the job.';
  }

  if (st === 'SCHEDULED') {
    return 'Use visit actions to set a time—confirm the client’s slot if they already proposed one.';
  }

  return 'Review job details and use the actions on the right to move this job forward.';
}

export function getEvidenceGuidance(wo) {
  if ((wo?.work_order_kind || '').toUpperCase() === 'COMPLIANCE' && wo?.expected_output_document_type) {
    return `Your client expects evidence that matches: ${wo.expected_output_document_type}. Upload clear, legible files — they may be used for compliance records.`;
  }
  return 'Upload photos, certificates, PDFs that show completed work. Your client reviews what you attach.';
}

/**
 * Strict next statuses for contractor PATCH (matches backend policy).
 * SCHEDULED → IN_PROGRESS | AWAITING_PARTS; IN_PROGRESS → AWAITING_PARTS | COMPLETED;
 * AWAITING_PARTS → IN_PROGRESS | COMPLETED. OPEN/ASSIGNED use Accept/Decline, not PATCH.
 */
const STRICT_CONTRACTOR_TRANSITIONS = {
  SCHEDULED: ['IN_PROGRESS', 'AWAITING_PARTS'],
  IN_PROGRESS: ['AWAITING_PARTS', 'COMPLETED'],
  AWAITING_PARTS: ['IN_PROGRESS', 'COMPLETED'],
};

export function getAllowedNextStatuses(wo) {
  const st = (wo?.status || '').toUpperCase();
  if (TERMINAL.has(st) || st === 'OPEN' || st === 'ASSIGNED') return [];
  return [...(STRICT_CONTRACTOR_TRANSITIONS[st] || [])];
}

export function statusValueToLabel(v) {
  return STATUS_LABELS[v] || v;
}

export function sortWorkOrdersForDashboard(workOrders, now = new Date()) {
  const list = [...(workOrders || [])];
  const score = (wo) => {
    let s = 0;
    if (isSlaOverdue(wo, now)) s += 1000;
    if (isPendingScheduling(wo)) s += 100;
    const due = parseIsoDate(wo?.sla_complete_by);
    if (due) s += (1e12 - due.getTime()) / 1e15;
    return s;
  };
  list.sort((a, b) => score(b) - score(a));
  return list;
}

const CONTRACTOR_PROGRESS_STEPS = ['Assigned', 'Scheduled', 'In progress', 'Completed', 'Closed'];

const EXECUTION_ACTIVE = new Set(['OPEN', 'ASSIGNED', 'SCHEDULED', 'IN_PROGRESS', 'AWAITING_PARTS']);

/** Work order is still in the execution pipeline (not completed / verified / closed / cancelled). */
export function isContractorExecutionActive(wo) {
  const st = (wo?.status || '').toUpperCase();
  return EXECUTION_ACTIVE.has(st);
}

/** Job has submit_invoice in next_actions (invoice-eligible). */
export function isContractorInvoiceEligible(wo) {
  return (wo?.next_actions || []).some((a) => a?.id === 'submit_invoice');
}

const CONTRACTOR_PUSH_ACTION_IDS = new Set([
  'accept_assignment',
  'decline_assignment',
  'confirm_visit',
  'upload_completion_proof',
  'submit_invoice',
  'edit_invoice',
  'submit_quote',
  'mark_inspection_complete',
  'start_job',
  'resume_job',
  'complete_job',
  'propose_visit',
  'awaiting_parts',
  'mark_no_access',
  'cancel_scheduled_visit',
  'reschedule_visit',
]);

/** Waiting on client / payment / clearance — not something the contractor can push right now. */
export function isContractorWaitingOnOthers(wo) {
  const ids = (wo?.next_actions || []).map((a) => a?.id).filter(Boolean);
  if (!ids.length) return false;
  if (ids.some((id) => CONTRACTOR_PUSH_ACTION_IDS.has(id))) return false;
  return ids.every((id) => id === 'open_job_detail' || id === 'view_invoice');
}

export function isScheduledTodayUtc(wo, now = new Date()) {
  const st = (wo?.status || '').toUpperCase();
  if (st === 'CANCELLED' || !wo?.scheduled_at) return false;
  try {
    const d = new Date(wo.scheduled_at);
    return (
      d.getUTCFullYear() === now.getUTCFullYear() &&
      d.getUTCMonth() === now.getUTCMonth() &&
      d.getUTCDate() === now.getUTCDate()
    );
  } catch {
    return false;
  }
}

/** Single dominant list CTA: server progress contract primary, else first executable action. */
export function contractorListPrimaryAction(wo) {
  const primary = wo?.progress_contract?.next_primary_action;
  if (primary?.id && primary.id !== 'none') return primary;

  const list = contractorPortalExecutableActions(wo);
  if (!list.length) return null;
  const withoutNav = list.filter((a) => a.id !== 'open_job_detail');
  const pick = withoutNav.length ? withoutNav[0] : list[0];
  return pick;
}

/** Drawer next-action presentation: waiting-on-client should not show a dead Open job button. */
export function contractorDrawerPrimaryPresentation(wo) {
  const primary = contractorListPrimaryAction(wo);
  if (!primary) return { mode: 'none' };
  if (primary.id === 'open_job_detail' && isContractorWaitingOnOthers(wo)) {
    return { mode: 'waiting', message: primary.hint || 'Waiting on your client.' };
  }
  return { mode: 'action', action: primary };
}

const DETAIL_PROGRESS_STEPS = ['Assigned', 'Scheduled', 'In progress', 'Proof uploaded', 'Completed', 'Closed'];

/**
 * Drawer progress — prefers server progress_contract_v1.
 */
export function contractorDetailExecutionProgressFromWorkOrder(wo) {
  const fromContract = progressTrackerFromContract(wo);
  if (fromContract) {
    return { steps: fromContract.steps, currentIndex: fromContract.currentIndex };
  }

  const steps = DETAIL_PROGRESS_STEPS;
  const st = (wo?.status || '').toUpperCase();
  if (st === 'CANCELLED') return { steps, currentIndex: -1 };
  if (st === 'VERIFIED' || st === 'CLOSED') return { steps, currentIndex: 5 };
  if (st === 'COMPLETED') return { steps, currentIndex: 4 };
  const proofRequired = !!wo?.completion_proof_required;
  const proofSatisfied = !!wo?.completion_proof_satisfied;
  if (proofRequired && !proofSatisfied && (st === 'IN_PROGRESS' || st === 'AWAITING_PARTS')) {
    return { steps, currentIndex: 3 };
  }
  if (st === 'IN_PROGRESS' || st === 'AWAITING_PARTS') return { steps, currentIndex: 2 };
  const schedOk = (wo?.schedule_status || '').toLowerCase() === 'confirmed' && !!wo?.scheduled_at;
  if (st === 'SCHEDULED' && schedOk) return { steps, currentIndex: 2 };
  if (st === 'SCHEDULED') return { steps, currentIndex: 1 };
  if (st === 'OPEN' || st === 'ASSIGNED') return { steps, currentIndex: 0 };
  return { steps, currentIndex: 0 };
}

/** Actions returned by GET /api/contractor/work-orders (next_actions). */
export function contractorPortalExecutableActions(wo) {
  return (wo?.next_actions || []).filter((a) => a && a.id && a.id !== 'none');
}

/** Job detail panel — execution row only (server-driven; no scheduling/billing/assignment here). */
export const CONTRACTOR_DETAIL_JOB_ACTION_IDS = new Set([
  'start_job',
  'awaiting_parts',
  'resume_job',
  'complete_job',
  'mark_inspection_complete',
]);

/**
 * Billing phase label for contractor job detail (uses invoice when present, else next_actions for ready-to-invoice).
 * @param {Record<string, unknown>|null|undefined} wo
 * @param {Record<string, Record<string, unknown>>|null|undefined} invoiceByWo
 */
export function contractorBillingPhaseForWorkOrder(wo, invoiceByWo) {
  const wid = wo?.work_order_id;
  const inv = wo?.linked_invoice || (invoiceByWo && wid ? invoiceByWo[wid] : null);
  const raw = (inv?.status || '').toLowerCase();
  const mapped = (inv?.contractor_invoice_state || '').toUpperCase();
  if (raw === 'paid' || mapped === 'PAID') return { key: 'paid', label: 'Paid' };
  if (raw === 'rejected' || mapped === 'REJECTED') return { key: 'rejected', label: 'Rejected' };
  if (raw === 'pending' || raw === 'needs_info') return { key: 'submitted', label: 'Submitted — awaiting client review' };
  if (raw === 'approved' || mapped === 'APPROVED') return { key: 'approved', label: 'Approved — arrange payment with client' };
  const na = wo?.next_actions || [];
  if (na.some((a) => a.id === 'submit_invoice')) return { key: 'ready', label: 'Ready to invoice' };
  return { key: 'not_ready', label: 'Not ready to invoice' };
}

/** Chronological timeline for job detail (oldest first). */
export function contractorDetailTimelineSorted(events) {
  if (!Array.isArray(events) || !events.length) return [];
  return [...events].sort((a, b) => {
    const ta = parseIsoDate(a?.at)?.getTime() ?? 0;
    const tb = parseIsoDate(b?.at)?.getTime() ?? 0;
    if (ta !== tb) return ta - tb;
    return String(a?.label || '').localeCompare(String(b?.label || ''));
  });
}

/** Button label for billing CTAs from next_actions (e.g. view → View payment when paid). */
export function contractorBillingActionButtonLabel(action, wo, invoiceByWo) {
  if (!action?.id) return '';
  if (action.id !== 'view_invoice') return action.label || '';
  const wid = wo?.work_order_id;
  const inv = wo?.linked_invoice || (invoiceByWo && wid ? invoiceByWo[wid] : null);
  const raw = (inv?.status || '').toLowerCase();
  if (raw === 'paid') return 'View payment';
  return action.label || 'View invoice';
}

export function contractorNextStepLineFromNextActions(wo) {
  const list = contractorPortalExecutableActions(wo);
  if (list.length === 0) return 'No action required';
  const a = list[0];
  return a.hint || a.label || '';
}

export function contractorPrimarySecondaryFromNextActions(wo) {
  const list = contractorPortalExecutableActions(wo);
  if (!list.length) return { primary: null, secondary: null };
  return { primary: list[0], secondary: list[1] || null };
}

export function contractorJobStatusLabel(wo) {
  const j = (wo?.job_status || wo?.status || '').toString().toUpperCase();
  const map = {
    OPEN: 'Open',
    ASSIGNED: 'Assigned',
    BOOKED: 'Booked',
    BOOKING_REQUESTED: 'Booking requested',
    SCHEDULED: 'Scheduled',
    IN_PROGRESS: 'In progress',
    AWAITING_PARTS: 'Awaiting parts',
    COMPLETED: 'Completed',
    VERIFIED: 'Verified',
    CLOSED: 'Closed',
    CANCELLED: 'Cancelled',
    NO_ACCESS: 'No access',
    RESCHEDULE_REQUIRED: 'Reschedule required',
    FOLLOW_UP_REQUIRED: 'Follow-up required',
    DRAFT: 'Draft',
  };
  return map[j] || (j ? j.replace(/_/g, ' ') : '—');
}

/** Progress strip: Assigned → Scheduled → In progress → Completed → Closed */
export function contractorProgressFromWorkOrder(wo) {
  const steps = CONTRACTOR_PROGRESS_STEPS;
  const st = (wo?.status || '').toUpperCase();
  const js = (wo?.job_status || '').toUpperCase();
  const schedOk =
    ((wo?.schedule_status || '').toLowerCase() === 'confirmed' && !!wo?.scheduled_at) || js === 'BOOKED';

  if (st === 'CANCELLED' || js === 'CANCELLED') {
    return { steps, currentIndex: -1 };
  }
  if (st === 'VERIFIED' || st === 'CLOSED' || js === 'VERIFIED' || js === 'CLOSED') {
    return { steps, currentIndex: 4 };
  }
  if (st === 'COMPLETED' || js === 'COMPLETED') {
    return { steps, currentIndex: 3 };
  }
  if (
    st === 'IN_PROGRESS' ||
    st === 'AWAITING_PARTS' ||
    js === 'IN_PROGRESS' ||
    js === 'AWAITING_PARTS' ||
    js === 'NO_ACCESS' ||
    js === 'RESCHEDULE_REQUIRED' ||
    js === 'FOLLOW_UP_REQUIRED'
  ) {
    return { steps, currentIndex: 2 };
  }
  if (schedOk || js === 'BOOKED' || (st === 'SCHEDULED' && schedOk)) {
    return { steps, currentIndex: 1 };
  }
  return { steps, currentIndex: 0 };
}
