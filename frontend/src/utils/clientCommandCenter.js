/**
 * Client Command Center — pure helpers for verdict copy, job attention ranking, and stuck signals.
 * Keeps UI pages from accumulating a second business-rules layer; aligns with API field names.
 */

const TERMINAL_WORK_ORDER_STATUSES = new Set(['COMPLETED', 'VERIFIED', 'CLOSED', 'CANCELLED']);

const PROOF_PENDING = 'NOT_SUBMITTED';
const BOOKING_AWAITING_CONTRACTOR = 'AWAITING_CONTRACTOR_RESPONSE';
const ROUTING_PENDING_CLIENT = 'PENDING_CLIENT_CONFIRMATION';

const SLA_DUE_SOON_HOURS = 72;

export function isActiveWorkOrder(wo) {
  if (!wo?.status) return false;
  return !TERMINAL_WORK_ORDER_STATUSES.has(String(wo.status).toUpperCase());
}

export function hasTruthyIso(field) {
  return field != null && String(field).trim() !== '';
}

function parseIsoMs(iso) {
  if (!iso || !String(iso).trim()) return null;
  try {
    const t = new Date(iso).getTime();
    return Number.isNaN(t) ? null : t;
  } catch {
    return null;
  }
}

function isComplianceWorkOrder(wo) {
  return String(wo?.work_order_kind || '').toUpperCase() === 'COMPLIANCE';
}

export function isAwaitingProof(wo) {
  if (!isComplianceWorkOrder(wo)) return false;
  const ps = String(wo.compliance_proof_status || '').toUpperCase();
  if (ps && ps !== PROOF_PENDING) return false;
  const st = String(wo.status || '').toUpperCase();
  if (['DRAFT', 'OPEN', 'CANCELLED'].includes(st)) return false;
  return true;
}

export function isOperationalHold(wo) {
  return !!(wo?.operational_exception && String(wo.operational_exception).trim());
}

function isAwaitingParts(wo) {
  return String(wo?.status || '').toUpperCase() === 'AWAITING_PARTS';
}

function isPendingContractorAction(wo) {
  const booking = String(wo?.compliance_booking_status || '').toUpperCase();
  if (booking === BOOKING_AWAITING_CONTRACTOR) return true;
  const st = String(wo.status || '').toUpperCase();
  const routing = String(wo?.assignment_routing_state || '').toUpperCase();
  if (routing === ROUTING_PENDING_CLIENT) return false;
  if (st === 'ASSIGNED' && wo.contractor_id && !hasTruthyIso(wo.accepted_at)) return true;
  return false;
}

function slaDueSoon(wo) {
  const dueMs = parseIsoMs(wo.sla_complete_by);
  if (dueMs == null) return false;
  const hours = (dueMs - Date.now()) / 3600000;
  return hours >= 0 && hours <= SLA_DUE_SOON_HOURS;
}

function workOrderAttentionSortKey(wo) {
  const st = String(wo.status || '').toUpperCase();
  const breached = hasTruthyIso(wo.sla_breached_at);
  const near = hasTruthyIso(wo.sla_breach_risk_at) && !breached;
  const opHold = isOperationalHold(wo);
  const proof = isAwaitingProof(wo);
  const parts = isAwaitingParts(wo);
  const pendingCx = isPendingContractorAction(wo);
  const scheduledSoon =
    st === 'SCHEDULED' || (slaDueSoon(wo) && ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'SCHEDULED'].includes(st));

  let tier = 7;
  if (breached) tier = 0;
  else if (near) tier = 1;
  else if (opHold) tier = 2;
  else if (proof) tier = 3;
  else if (parts) tier = 4;
  else if (pendingCx) tier = 5;
  else if (scheduledSoon) tier = 6;

  const dueMs = parseIsoMs(wo.sla_complete_by);
  const dueKey = dueMs == null ? Number.POSITIVE_INFINITY : dueMs;

  return { tier, dueKey, wo };
}

function compareAttentionKeys(a, b) {
  if (a.tier !== b.tier) return a.tier - b.tier;
  return a.dueKey - b.dueKey;
}

/**
 * Active jobs ordered by operational attention (SLA, holds, proof, contractor, due soon), then SLA date.
 */
export function rankWorkOrdersByAttention(activeList, limit = 8) {
  if (!Array.isArray(activeList)) return [];
  return activeList
    .map((wo) => workOrderAttentionSortKey(wo))
    .sort(compareAttentionKeys)
    .map((x) => x.wo)
    .slice(0, limit);
}

export function attentionBadgeForJob(wo) {
  if (hasTruthyIso(wo.sla_breached_at)) return { label: 'SLA overdue', className: 'bg-red-100 text-red-900' };
  if (hasTruthyIso(wo.sla_breach_risk_at)) return { label: 'SLA at risk', className: 'bg-amber-100 text-amber-900' };
  if (isOperationalHold(wo)) {
    const raw = String(wo.operational_exception || '').replace(/_/g, ' ').toLowerCase();
    return { label: raw ? `On hold (${raw})` : 'On hold', className: 'bg-amber-100 text-amber-900' };
  }
  if (isAwaitingProof(wo)) return { label: 'Awaiting proof', className: 'bg-violet-100 text-violet-900' };
  if (isAwaitingParts(wo)) return { label: 'Awaiting parts', className: 'bg-slate-200 text-slate-900' };
  if (isPendingContractorAction(wo)) return { label: 'With contractor', className: 'bg-sky-100 text-sky-900' };
  if (slaDueSoon(wo)) return { label: 'Due soon', className: 'bg-teal-100 text-teal-900' };
  return null;
}

export function countPropertiesAtRisk(portfolioSummary) {
  const props = portfolioSummary?.properties;
  if (!Array.isArray(props)) return 0;
  let n = 0;
  for (const p of props) {
    const overdue = Number(p.overdue_count ?? 0) > 0;
    const score = p.property_score != null ? Number(p.property_score) : p.score != null ? Number(p.score) : null;
    const risk = String(p.risk_level || '').toLowerCase();
    const badScore = score != null && !Number.isNaN(score) && score < 60;
    const badRisk = /high|severe|critical/.test(risk);
    if (overdue || badScore || badRisk) n += 1;
  }
  return n;
}

export function aggregateJobSignals(activeList) {
  let awaitingProof = 0;
  let onHoldOrParts = 0;
  let pendingContractor = 0;
  const holdIds = new Set();
  for (const wo of activeList) {
    if (isAwaitingProof(wo)) awaitingProof += 1;
    if (isOperationalHold(wo) || isAwaitingParts(wo)) {
      if (!holdIds.has(wo.work_order_id)) {
        holdIds.add(wo.work_order_id);
        onHoldOrParts += 1;
      }
    }
    if (isPendingContractorAction(wo)) pendingContractor += 1;
  }
  return { awaitingProof, onHoldOrParts, pendingContractor };
}

/**
 * @returns {{ line: string, subline: string|null, tone: 'calm'|'watch'|'critical' }}
 */
export function buildCommandCenterVerdict({
  urgentCount,
  riskCount,
  predictiveEnabled,
  summary,
  propertiesAtRisk,
  breachedJobCount,
  blockedJobCount,
  awaitingProofCount,
}) {
  const sublines = [];

  if (urgentCount > 0) {
    const line =
      urgentCount === 1
        ? '1 priority needs your attention today.'
        : `${urgentCount} priorities need your attention today.`;
    if (breachedJobCount > 0) {
      sublines.push(
        breachedJobCount === 1
          ? 'One job is past its SLA deadline.'
          : `${breachedJobCount} jobs are past their SLA deadline.`
      );
    } else if (blockedJobCount > 0) {
      sublines.push(
        blockedJobCount === 1 ? 'A job is blocked or on hold.' : `${blockedJobCount} jobs are blocked or on hold.`
      );
    }
    return { line, subline: sublines[0] || null, tone: 'critical' };
  }

  if (breachedJobCount > 0) {
    const line =
      breachedJobCount === 1
        ? 'A job is past its SLA deadline—follow up now.'
        : `${breachedJobCount} jobs are past their SLA deadline.`;
    if (blockedJobCount > 0) {
      sublines.push(`${blockedJobCount} job${blockedJobCount === 1 ? '' : 's'} also on hold or blocked.`);
    }
    return { line, subline: sublines[0] || null, tone: 'critical' };
  }

  if (blockedJobCount > 0) {
    const line =
      blockedJobCount === 1
        ? 'A job is blocked or on hold and needs follow-up.'
        : `${blockedJobCount} jobs are blocked or on hold.`;
    if (awaitingProofCount > 0) {
      sublines.push(
        awaitingProofCount === 1
          ? 'One job is still awaiting proof of completion.'
          : `${awaitingProofCount} jobs are awaiting proof of completion.`
      );
    }
    return { line, subline: sublines[0] || null, tone: 'watch' };
  }

  if (awaitingProofCount > 0) {
    return {
      line:
        awaitingProofCount === 1
          ? 'A job is awaiting proof of completion.'
          : `${awaitingProofCount} jobs are awaiting proof of completion.`,
      subline: null,
      tone: 'watch',
    };
  }

  const overdueReq = summary?.requirements_overdue != null ? Number(summary.requirements_overdue) : 0;
  if (overdueReq > 0) {
    return {
      line:
        overdueReq === 1
          ? '1 compliance requirement is overdue.'
          : `${overdueReq} compliance requirements are overdue.`,
      subline: null,
      tone: 'critical',
    };
  }

  if (propertiesAtRisk === 1) {
    return {
      line: '1 property is at compliance risk.',
      subline: null,
      tone: 'watch',
    };
  }
  if (propertiesAtRisk > 1) {
    return {
      line: `${propertiesAtRisk} properties need compliance attention.`,
      subline: null,
      tone: 'watch',
    };
  }

  if (predictiveEnabled && riskCount > 0) {
    return {
      line: riskCount === 1 ? '1 active risk signal needs review.' : `${riskCount} active risk signals need review.`,
      subline: null,
      tone: 'watch',
    };
  }

  const color = String(summary?.color || '').toLowerCase();
  if (color === 'amber' || color === 'red') {
    return {
      line: summary?.message?.trim() || 'Review compliance status—there is room to improve.',
      subline: null,
      tone: color === 'red' ? 'critical' : 'watch',
    };
  }

  return {
    line: "You're on track.",
    subline: null,
    tone: 'calm',
  };
}

export function isCommandCenterAllClearEmpty({
  urgentCount,
  predictiveEnabled,
  riskCount,
  activeJobsLength,
  summary,
  propertiesAtRisk,
}) {
  return (
    urgentCount === 0 &&
    (!predictiveEnabled || riskCount === 0) &&
    activeJobsLength === 0 &&
    (summary?.requirements_overdue == null || Number(summary.requirements_overdue) === 0) &&
    propertiesAtRisk === 0 &&
    String(summary?.color || '').toLowerCase() === 'green'
  );
}

export function isCommandCenterCalmSnapshot({
  urgentCount,
  predictiveEnabled,
  riskCount,
  breachedJobCount,
  blockedJobCount,
  summary,
  propertiesAtRisk,
}) {
  return (
    urgentCount === 0 &&
    (!predictiveEnabled || riskCount === 0) &&
    breachedJobCount === 0 &&
    blockedJobCount === 0 &&
    (summary?.requirements_overdue == null || Number(summary.requirements_overdue) === 0) &&
    propertiesAtRisk === 0
  );
}
