/**
 * Client Command Center — pure helpers for verdict copy, job attention ranking, and stuck signals.
 * Keeps UI pages from accumulating a second business-rules layer; aligns with API field names.
 */
import { operationalExceptionLabel, inboxTitleForDisplay } from '../domain/presentDomain';
import { compareTopPriority, normalizeTaskForTopPriorityRanking } from './clientTopPriorityRanking';
import {
  clientInboxJobCtaLabel,
  normalizeClientJobCtaLabelFromApi,
  CLIENT_INBOX_JOB_FALLBACK_CTA,
} from './jobWorkflowUi';

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
    const ex = String(wo.operational_exception || '').trim();
    const human = ex ? operationalExceptionLabel(ex) : '';
    return { label: human ? `On hold (${human})` : 'On hold', className: 'bg-amber-100 text-amber-900' };
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
        blockedJobCount === 1 ? 'A job is on hold.' : `${blockedJobCount} jobs are on hold.`
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
      sublines.push(`${blockedJobCount} job${blockedJobCount === 1 ? '' : 's'} also on hold.`);
    }
    return { line, subline: sublines[0] || null, tone: 'critical' };
  }

  if (blockedJobCount > 0) {
    const line =
      blockedJobCount === 1
        ? 'A job is on hold—needs follow-up.'
        : `${blockedJobCount} jobs are on hold.`;
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
      line: riskCount === 1 ? '1 open issue needs review.' : `${riskCount} open issues need review.`,
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

/** Generic job open verbs from API → softer inbox language before we infer a concrete step. */
const COMMAND_CENTER_GENERIC_JOB_KEYS = new Set(['view job', 'open job']);

const COMMAND_CENTER_CTA_LABEL_MAP = {
  'view job': CLIENT_INBOX_JOB_FALLBACK_CTA,
  'open job': CLIENT_INBOX_JOB_FALLBACK_CTA,
  'review risk signal': 'Review flagged issue',
  'view risk signal': 'Review flagged issue',
};

/**
 * Command Center row primary CTA (existing task fields only).
 *
 * Resolution order:
 * 1. If primary label is a mapped generic job key (view/open job) and task is work_order: `clientInboxJobCtaLabel` else `CLIENT_INBOX_JOB_FALLBACK_CTA`.
 * 2. Else other map entries (e.g. risk signal phrasing).
 * 3. Else non-empty primary label: for work orders, `normalizeClientJobCtaLabelFromApi`; else as-is.
 * 4. Else by metadata / source_type (upload, requirement, work_order → clientInboxJobCtaLabel || fallback, risk, issue, approval).
 * 5. Else `Continue in Today`.
 */
export function sanitizeCommandCenterCtaLabel(primaryLabel, task) {
  const candidate = String(primaryLabel || task?.primary_action_label || task?.primary_cta?.label || '').trim();
  const key = candidate.toLowerCase();
  const stLower = String(task?.source_type || '').toLowerCase();
  const mapped = COMMAND_CENTER_CTA_LABEL_MAP[key];
  if (mapped) {
    if (COMMAND_CENTER_GENERIC_JOB_KEYS.has(key) && stLower === 'work_order') {
      return clientInboxJobCtaLabel(task) || CLIENT_INBOX_JOB_FALLBACK_CTA;
    }
    return mapped;
  }
  if (candidate) {
    if (stLower === 'work_order') return normalizeClientJobCtaLabelFromApi(candidate);
    return candidate;
  }

  const meta = task?.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const at = String(meta.action_type || '');
  const st = String(task?.source_type || '');
  const pat = String(task?.primary_action_type || task?.action_type || '');

  if (at === 'missing_document' || pat === 'upload_evidence') return 'Upload document';
  if (at === 'overdue_compliance' || at === 'certificate_expiring_soon') return 'Review requirement';
  if (st === 'work_order' || /work_order/i.test(at)) {
    return clientInboxJobCtaLabel(task) || CLIENT_INBOX_JOB_FALLBACK_CTA;
  }
  if (st === 'risk_signal' || at === 'risk_signal') return 'Review flagged issue';
  if (st === 'issue') return 'Review issue';
  if (st === 'approval') return 'Review approval';
  if (st === 'requirement') return 'Review requirement';
  return 'Continue in Today';
}

/**
 * Specific, urgency-driven line for Command Center property rows (uses API fields only).
 */
export function commandCenterWhyThisMattersLine(task) {
  const meta = task?.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const name = inboxTitleForDisplay(task);
  const label = name && name !== 'Task' ? name : 'Requirement';
  const at = String(meta.action_type || '');
  const st = String(task?.source_type || '');
  const od = Number(task.overdue_days ?? meta.overdue_days ?? 0);
  const impact = String(task?.impact_label || '').trim().toLowerCase();

  const impactClause = impact && !impact.includes('review') ? ` (${impact})` : '';

  if (at === 'overdue_compliance' && od > 0) {
    return `${label} — overdue by ${od} day${od === 1 ? '' : 's'}${impactClause || ' (compliance risk)'}`;
  }
  if (at === 'certificate_expiring_soon') {
    return `${label} — due soon${impactClause}`;
  }
  if (at === 'missing_document') {
    return `${label} — document not uploaded${impactClause || ' (blocks evidence)'}`;
  }
  if (at === 'work_order_sla_breached') {
    const jobName = label !== 'Requirement' ? label : 'Job';
    return `${jobName} — SLA deadline passed${impactClause}`;
  }
  if (at === 'work_order_near_sla_breach') {
    const jobName = label !== 'Requirement' ? label : 'Job';
    return `${jobName} — SLA at risk${impactClause}`;
  }
  if (at === 'risk_signal' || st === 'risk_signal') {
    return `${label} — flagged issue needs review${impactClause}`;
  }
  if (at === 'open_operational_issue' || st === 'issue') {
    return `${label} — issue needs review${impactClause}`;
  }
  if (at === 'open_work_order' || st === 'work_order') {
    const jobName = label !== 'Requirement' ? label : 'Job';
    const hay = `${String(task?.title || '')} ${String(task?.description || '')}`.toLowerCase();
    const visitCue = /visit|schedule|booking|booked|proposed/.test(hay);
    const contractorCue = /contractor|assigned|accept/.test(hay);
    let stateLine = 'Work in progress';
    if (visitCue) stateLine = 'Visit scheduled — awaiting completion';
    else if (contractorCue) stateLine = 'Waiting on contractor';
    return `${jobName} — ${stateLine}${impactClause}`;
  }
  if (at === 'pending_invoice_approval' || st === 'approval') {
    return `${label} — invoice needs your approval${impactClause}`;
  }

  const timing = String(meta.timing_label || task?.timing_label || '').trim();
  if (timing && label !== 'Requirement') return `${label} — ${timing.charAt(0).toLowerCase() + timing.slice(1)}`;
  if (timing) return timing;
  if (label && label !== 'Requirement') return `${label} — continue in Today for the next step`;
  return 'Continue in Today for the next step';
}

/**
 * One representative task per property, ranked like Today’s top-priority ordering.
 * @param {unknown[]} urgentActions
 * @param {number} [limit]
 */
export function buildPropertyPriorityRepresentatives(urgentActions, limit = 8) {
  if (!Array.isArray(urgentActions)) return [];
  const byProp = new Map();
  for (const raw of urgentActions) {
    const task = normalizeTaskForTopPriorityRanking(raw);
    const pid = task.property_id;
    if (!pid) continue;
    const prev = byProp.get(pid);
    if (!prev || compareTopPriority(task, prev) < 0) byProp.set(pid, task);
  }
  const reps = [...byProp.values()];
  reps.sort(compareTopPriority);
  return reps.slice(0, limit);
}

function countUrgentByMeta(urgentActions, predicate) {
  if (!Array.isArray(urgentActions)) return 0;
  let n = 0;
  for (const raw of urgentActions) {
    const meta = raw?.metadata && typeof raw.metadata === 'object' ? raw.metadata : {};
    if (predicate(raw, meta)) n += 1;
  }
  return n;
}

/**
 * Portfolio pressure metrics (single source for verdict + UI highlight on improvement).
 */
export function computePortfolioDriverMetrics({
  summary,
  portfolioSummary,
  urgentActions,
  breachedJobCount,
  blockedJobCount,
  awaitingProofJobCount = 0,
}) {
  const overdueSummary = summary?.requirements_overdue != null ? Number(summary.requirements_overdue) : 0;
  const overdueKpi = portfolioSummary?.kpis?.overdue != null ? Number(portfolioSummary.kpis.overdue) : 0;
  const overdueFromTasks = countUrgentByMeta(urgentActions || [], (_, meta) => meta.action_type === 'overdue_compliance');
  const overdueDisplay = Math.max(overdueSummary, overdueKpi, overdueFromTasks);

  const missingKpi = portfolioSummary?.kpis?.missing != null ? Number(portfolioSummary.kpis.missing) : 0;
  const missingFromTasks = countUrgentByMeta(urgentActions || [], (_, meta) => meta.action_type === 'missing_document');
  const missingDisplay = Math.max(missingKpi, missingFromTasks);

  const jobPressure =
    (Number(breachedJobCount) || 0) + (Number(blockedJobCount) || 0) + (Number(awaitingProofJobCount) || 0);

  return { overdueDisplay, missingDisplay, jobPressure };
}

/**
 * Portfolio-level synthesis: status, drivers, best next move (existing API fields only).
 */
export function buildPortfolioVerdictBlock({
  summary,
  portfolioSummary,
  urgentCount,
  urgentActions,
  riskCount,
  predictiveEnabled,
  breachedJobCount,
  blockedJobCount,
  awaitingProofJobCount = 0,
}) {
  const { overdueDisplay, missingDisplay, jobPressure } = computePortfolioDriverMetrics({
    summary,
    portfolioSummary,
    urgentActions,
    breachedJobCount,
    blockedJobCount,
    awaitingProofJobCount,
  });

  const riskFromTasks = countUrgentByMeta(
    urgentActions,
    (t, meta) => meta.action_type === 'risk_signal' || t?.source_type === 'risk_signal'
  );
  const riskDisplay = predictiveEnabled ? Math.max(riskCount || 0, riskFromTasks) : riskFromTasks;

  const drivers = [];
  if (overdueDisplay > 0) {
    drivers.push({
      key: 'overdue',
      label:
        overdueDisplay === 1
          ? '1 overdue requirement — resolve it first'
          : `${overdueDisplay} overdue requirements — resolve these first`,
    });
  }
  if (missingDisplay > 0) {
    drivers.push({
      key: 'missing',
      label:
        missingDisplay === 1
          ? '1 missing document — upload to reduce risk'
          : `${missingDisplay} missing documents — upload to reduce risk`,
    });
  }
  if (jobPressure > 0) {
    drivers.push({
      key: 'job_pressure',
      label:
        jobPressure === 1
          ? '1 job blocking progress — unblock to restore momentum'
          : `${jobPressure} jobs blocking progress — unblock to restore momentum`,
    });
  }
  if (riskDisplay > 0) {
    drivers.push({
      key: 'risk',
      label:
        riskDisplay === 1
          ? '1 open issue — review and resolve'
          : `${riskDisplay} open issues — review and resolve`,
    });
  }

  const color = String(summary?.color || '').toLowerCase();
  let statusLabel = 'On track';
  let statusTone = 'calm';
  if (breachedJobCount > 0 || color === 'red') {
    statusLabel = 'Critical attention';
    statusTone = 'critical';
  } else if (urgentCount > 0 || jobPressure > 0 || drivers.length > 0 || color === 'amber') {
    statusLabel = 'Attention needed';
    statusTone = 'watch';
  }

  /** Dominant bucket: highest count wins; ties break overdue → missing → jobs (compliance-first). */
  const buckets = [
    { key: 'overdue', n: overdueDisplay },
    { key: 'missing', n: missingDisplay },
    { key: 'jobs', n: jobPressure },
  ];
  const maxN = Math.max(overdueDisplay, missingDisplay, jobPressure, 0);

  let bestNextMove = '';
  let nextHintPath = '/today';
  let nextHintLabel = 'Continue in Today';

  if (maxN > 0) {
    const winner = buckets.find((b) => b.n === maxN);
    if (winner.key === 'overdue') {
      nextHintPath = '/requirements';
      nextHintLabel = 'Continue in Requirements';
      bestNextMove = 'Start with overdue requirements — resolve these first.';
    } else if (winner.key === 'missing') {
      nextHintPath = '/documents';
      nextHintLabel = 'Continue in Documents';
      bestNextMove = 'Upload missing documents to reduce risk.';
    } else {
      nextHintPath = '/operations/work-orders';
      nextHintLabel = 'Continue in Jobs';
      bestNextMove = 'Resolve blocked jobs to restore progress.';
    }
  } else if (predictiveEnabled && (riskCount || 0) > 0) {
    const rc = riskCount || 0;
    nextHintPath = '/operations/risk-signals';
    nextHintLabel = 'Review flagged issues';
    bestNextMove =
      rc === 1
        ? 'One flagged issue needs a decision — review it now.'
        : `${rc} flagged issues need decisions — review them now.`;
  } else if (urgentCount > 0) {
    nextHintPath = '/today';
    nextHintLabel = 'Continue in Today';
    bestNextMove =
      urgentCount === 1
        ? 'Your top urgent item is not fully reflected in the counts above — continue in Today and resolve it first.'
        : `${urgentCount} urgent items need attention — continue in Today and work from the top down.`;
  } else {
    nextHintPath = '/today';
    nextHintLabel = 'Continue in Today';
    bestNextMove =
      'Portfolio snapshot looks clear — continue in Today for the full queue and the next concrete step.';
  }

  const driverSummaryFallback =
    drivers.length > 0
      ? ''
      : maxN > 0
        ? 'Follow “What to do next” for the strongest portfolio signal.'
        : urgentCount > 0
          ? 'Urgent work lives in Today — use the button below and start at the top.'
          : 'Light portfolio pressure right now — continue in Today when you are ready for the next step.';

  return {
    statusLabel,
    statusTone,
    drivers,
    bestNextMove,
    nextHintPath,
    nextHintLabel,
    driverSummaryFallback,
  };
}
