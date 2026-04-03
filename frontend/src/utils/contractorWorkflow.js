/**
 * Contractor portal: lifecycle stages, prioritisation, next-step copy, and allowed status transitions.
 * Aligns with backend maintenance_service work order statuses and invoice approval flow.
 */

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
    return 'Your invoice was rejected. Check your email or contact the client, then submit a revised invoice if they allow it.';
  }
  if (invSt === 'needs_info') return 'The client needs more information on your invoice. Respond via their request, then resubmit if applicable.';

  if (invSt === 'approved') {
    return 'Invoice approved — payment is arranged with the client. Follow up with them if you have not received funds.';
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
        : ' Upload evidence (photos or certificates) when work is finished.';
    return `Complete the work on site, then mark the job complete.${docHint}`;
  }

  if ((wo?.schedule_status || '').toLowerCase() === 'confirmed' && wo?.scheduled_at) {
    try {
      const d = new Date(wo.scheduled_at);
      const when = d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
      return `Attend the visit on ${when}. Mark in progress when you arrive, or request a change if you cannot attend.`;
    } catch {
      return 'Attend the scheduled visit. Mark in progress when you arrive.';
    }
  }

  if ((wo?.schedule_status || '').toLowerCase() === 'proposed') {
    const sb = (wo?.scheduled_by || '').toLowerCase();
    if (sb === 'client' || sb === 'admin') {
      return 'Confirm the proposed visit time, or propose a different time.';
    }
    return 'Waiting for the client to confirm your proposed visit time.';
  }

  if (st === 'OPEN' || st === 'ASSIGNED') {
    return 'Accept the assignment to unlock scheduling and evidence upload, or decline if you cannot take the job.';
  }

  if (st === 'SCHEDULED') {
    return 'Propose a visit date and time, or confirm one the client has proposed.';
  }

  return 'Review job details and use the actions on the right to move this job forward.';
}

export function getEvidenceGuidance(wo) {
  if ((wo?.work_order_kind || '').toUpperCase() === 'COMPLIANCE' && wo?.expected_output_document_type) {
    return `Your client expects evidence that matches: ${wo.expected_output_document_type}. Upload clear, legible files — they may be used for compliance records.`;
  }
  return 'Upload photos, certificates, or PDFs that show the work completed. Files are visible to your client for review.';
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
