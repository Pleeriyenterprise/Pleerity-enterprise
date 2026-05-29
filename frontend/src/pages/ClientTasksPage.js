/**
 * Client portal — Today (priorities inbox). Aggregated server-side tasks with sections,
 * urgency, deep links, and selective inline actions (risk → issue / work order).
 *
 * Compliance KPI truth (overdue counts, score stats, requirement aggregates) lives in
 * ``/client/compliance-score``, dashboard, and reports — not in this task inbox. Today lists
 * **operational priorities** (unified tasks: requirements, jobs, risks, approvals) for actioning;
 * do not treat task counts as canonical compliance score inputs.
 *
 * Today model (keep aligned with docs/CLIENT_PORTAL_WORKFLOW_MATRIX.md and today_projection_service.py):
 *
 * - Business actions: server-provided `business_actions` (upload certificate → navigate to documents vault
 *   with focus=upload; compliance inspection job → POST requirement job then navigate; view requirement/issue/job;
 *   etc.). These drive real domain workflows, not inbox presentation alone.
 *
 * - Visibility actions: `visibility_actions` → POST /api/today/items/{id}/snooze | mark-reviewed | dismiss.
 *   These are Today visibility only (overrides); they do not upload documents, satisfy requirements, close jobs, or resolve issues.
 *
 * Analytics: `TODAY_TASK_COMPLETED` = inbox visibility only (mark reviewed), not underlying object resolved.
 * Workflow attempts: `TODAY_PRIMARY_ACTION_TRIGGERED` (see backend `product_analytics_service` module doc).
 *
 * - Restore: hidden/dismissed items expose restore → POST /api/today/items/{id}/restore (see restoreTodayItem).
 *   Clears overrides so the task can reappear; does not mutate underlying requirement/job/document state.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  inboxTitleForDisplay,
  requirementDisplayTitle,
  requirementLabel,
  inboxSourceTypeLabel,
  inboxTimelineActionLabel,
} from '../domain/presentDomain';
import domainLabels from '../domain/domain_labels.json';
import {
  workOrderKindClientLabel,
  clientInboxJobCtaLabel,
  CLIENT_INBOX_JOB_FALLBACK_CTA,
} from '../utils/jobWorkflowUi';
import { useNavigate, Link } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { PortalSectionSkeleton, PortalStaleRefreshBanner } from '../components/client/ClientPortalPatterns';
import {
  fetchOperational,
  OPERATIONAL_CACHE_KEYS,
} from '../utils/clientOperationalFetch';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { useGuidedEvidenceModal } from '../context/GuidedEvidenceModalContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Loader2, LayoutList, Info, ExternalLink, Bell, EyeOff, CheckCircle, RotateCcw, History, AlertCircle } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import { TodayUrgencyRow } from '../components/client/UrgencyDisplay';
import {
  resolveClientPortalPath,
  continueWorkspaceCtaLabel,
  isSafeClientPortalPath,
  buildSafeQueryPath,
} from '../utils/clientPortalNavigation';
import { HELP_ARTICLE_SLUG_INBOX_VISIBILITY_TODAY } from '../content/helpArticleFallbacks';
import { PlanRestrictedJobModal, openPlanRestrictedJobGate } from '../components/client/PlanRestrictedActionModal';
import { portfolioJurisdictionBannerState } from '../utils/jurisdictionUiPolicy';
import { resolveTaskCta } from '../utils/ctaRegistry';
import {
  JURISDICTION_FALLBACK_ALERT_BODY,
  JURISDICTION_FALLBACK_ALERT_TITLE,
  JURISDICTION_FALLBACK_CTA,
  JURISDICTION_PORTFOLIO_REMINDER_COMPACT,
} from '../utils/jurisdictionComplianceCopy';
import {
  TODAY_PAGE_CONFIDENCE_LINE,
  todayTaskConfidenceLine,
  todayTaskSourceAttributionLine,
  shouldShowTodayTaskConfidence,
} from '../utils/confidenceUxCopy';
import { WORKSPACE_TODAY_PRIMARY, WORKSPACE_TODAY_VS_DASHBOARD } from '../utils/workspaceOrientationCopy';
import {
  shapeTodayBusinessActions,
  businessActionNavigatePath,
  stripTechnicalParenTail,
} from '../utils/todayWorkflowPolicy';
import { getPropertyDisplayName } from '../utils/propertyDisplayName';
import { todayRequirementWhyItMattersLine } from '../utils/todayRequirementWhyItMatters';
import { todayTaskOperationalGuidance } from '../utils/todayTaskOperationalGuidance';
import {
  alignTodayPayloadTaskSections,
  inboxTaskLinkedRequirementId,
  requirementMapFromList,
} from '../utils/portalRequirementAttention';
import { buildRequirementShapedRowFromPriorityTask } from '../utils/taskRequirementRowAdapter';
import {
  combineEvidenceSummaryWithResolvedSubline,
  projectResolvedRequirementSemantics,
} from '../utils/resolvedRequirementViewModel';
import TodayExecutionHero from '../components/client/TodayExecutionHero';
import ListCognitionChip from '../components/operational/ListCognitionChip';
import {
  buildOperationalSections,
  buildPropertyByIdMap,
  buildFalseEmptyStateDisclosure,
  enrichTaskForExecution,
  pickPrimaryExecutionTask,
  visibleOpenCount,
} from '../utils/todayExecutionWorkspace';

const FILTER_CHIPS = [
  { id: 'all', label: 'All' },
  { id: 'compliance', label: 'Requirements' },
  { id: 'operations', label: 'Operations' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'billing', label: 'Billing' },
  { id: 'risks', label: 'Issues' },
  { id: 'overdue', label: 'Overdue' },
];

function formatMoney(amount, currency = 'GBP') {
  if (amount == null || Number.isNaN(Number(amount))) return '\u2014';
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: currency || 'GBP' }).format(Number(amount));
}

function formatWhen(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return null;
  }
}

function sourceTypeLabel(st) {
  return inboxSourceTypeLabel(st);
}

/** Badge on Today cards: job kind from metadata when source is a work order, else friendly source. */
function todayTaskCategoryBadge(task) {
  const st = String(task?.source_type || '').toLowerCase();
  const meta = task?.metadata || {};
  if (st === 'work_order') {
    return workOrderKindClientLabel({ work_order_kind: meta.work_order_kind });
  }
  return sourceTypeLabel(st);
}

const TODAY_GENERIC_JOB_KEYS = new Set(['view job', 'open job']);

const TODAY_CTA_LABEL_MAP = {
  'view job': CLIENT_INBOX_JOB_FALLBACK_CTA,
  'open job': CLIENT_INBOX_JOB_FALLBACK_CTA,
  'review risk signal': 'Review risk signal',
  'view risk signal': 'Open risk signal',
  'review flagged issue': 'Review risk signal',
  'create job': 'Start maintenance job',
  'create compliance job': 'Create compliance job',
  'create issue': 'Log maintenance issue',
  'upload certificate': 'Upload compliance evidence',
};

/**
 * Today card primary CTA label (server `primary_action_label` / business_actions).
 * Order: (1) generic job keys → clientInboxJobCtaLabel || CLIENT_INBOX_JOB_FALLBACK_CTA; (2) other map; (3) empty + work_order → same; (4) empty → Continue in Today; (5) raw candidate.
 */
function sanitizeTodayCtaLabel(primaryLabel, task) {
  const metaTake = task?.metadata?.take_action;
  if (metaTake?.primary?.label) return String(metaTake.primary.label).trim();
  const fromBiz = (task?.business_actions || []).find((a) => a.primary === true || a.id === 'open_primary');
  const candidate = String(primaryLabel || fromBiz?.label || '').trim();
  const key = candidate.toLowerCase();
  if (TODAY_CTA_LABEL_MAP[key]) {
    const mapped = TODAY_CTA_LABEL_MAP[key];
    if (TODAY_GENERIC_JOB_KEYS.has(key) && task) {
      const specific = clientInboxJobCtaLabel(task);
      if (specific) return specific;
      return CLIENT_INBOX_JOB_FALLBACK_CTA;
    }
    return mapped;
  }
  if (!candidate) {
    if (String(task?.source_type || '').toLowerCase() === 'work_order') {
      return clientInboxJobCtaLabel(task) || CLIENT_INBOX_JOB_FALLBACK_CTA;
    }
    return 'Review task';
  }
  return candidate;
}

function sanitizeBusinessActionLabel(label) {
  const s = String(label || '').trim();
  const key = s.toLowerCase();
  if (TODAY_CTA_LABEL_MAP[key]) return TODAY_CTA_LABEL_MAP[key];
  return s;
}

/** Drop secondary business_actions that navigate to the same place as the primary button. */
function dedupeActionsByPrimaryPath(ordered) {
  if (!Array.isArray(ordered) || ordered.length <= 1) return ordered || [];
  const primary = ordered[0];
  const pp = businessActionNavigatePath(primary);
  const rest = [];
  for (let i = 1; i < ordered.length; i += 1) {
    const a = ordered[i];
    const ap = businessActionNavigatePath(a);
    if (pp && ap && pp === ap) continue;
    rest.push(a);
  }
  return [primary, ...rest];
}

function labelForTodayBusinessAction(act, task, workflow) {
  if (!act) return sanitizeTodayCtaLabel(task?.primary_action_label, task);
  if (String(act.action_authority) === 'take_action') {
    return String(act.label || '').trim();
  }
  if (String(act.id) === 'upload_certificate' && workflow === 'compliance') {
    return 'Upload compliance evidence';
  }
  if (String(act.id) === 'create_compliance_work_order' && workflow === 'compliance') {
    return 'Create compliance job';
  }
  if (String(act.id) === 'create_maintenance_job' && workflow === 'maintenance') {
    return 'Start maintenance job';
  }
  if (String(act.id) === 'view_job') {
    return clientInboxJobCtaLabel(task) || CLIENT_INBOX_JOB_FALLBACK_CTA;
  }
  if (workflow === 'unclear' && String(act.id) === 'open_primary') {
    const fb = sanitizeTodayCtaLabel(task?.primary_action_label, task);
    if (fb && fb !== 'Review task') return fb;
  }
  return sanitizeBusinessActionLabel(act.label);
}

function propertyOptionLabel(p) {
  if (!p) return 'Property';
  return getPropertyDisplayName(p) || 'Property';
}

/** Mirrors `domain_labels.json` → `today_inbox_action_titles` (generic inbox titles to replace locally). */
const GENERIC_TODAY_INBOX_TITLES = new Set(
  Object.values(domainLabels.today_inbox_action_titles || {}).map((s) => String(s).trim().toLowerCase()),
);

/** Decision-layer title: `{Name} — {state}` when the inbox title is generic. */
function todayDecisionLayerTitle(task) {
  const base = inboxTitleForDisplay(task);
  const rawTitle = String(task?.title || '').trim();
  const low = rawTitle.toLowerCase();
  if (!GENERIC_TODAY_INBOX_TITLES.has(low)) return base;

  const meta = task.metadata || {};
  const code = meta.requirement_code || meta.requirement_type;
  const u = String(task.urgency || task.urgency_level || '').toLowerCase();
  const od = Number(task.overdue_days || 0) > 0;
  const timing = String(meta.timing_label || '').trim();
  const stateFromTiming = timing ? timing.charAt(0).toLowerCase() + timing.slice(1) : '';

  if (task.source_type === 'work_order') {
    const jobLine = String(task.description || '').trim();
    if (code) {
      const name =
        requirementDisplayTitle(meta.requirement_display, 'compact') || requirementLabel(code);
      if (stateFromTiming) return `${name} — ${stateFromTiming}`;
      if (od || u === 'overdue') return `${name} — overdue`;
      if (u === 'due_soon' || u === 'high') return `${name} — due soon`;
      return `${name} — needs attention`;
    }
    if (jobLine.length > 12) return jobLine.length > 160 ? `${jobLine.slice(0, 157)}…` : jobLine;
    return base;
  }

  if (task.source_type === 'risk_signal') {
    if (code) {
      const name =
        requirementDisplayTitle(meta.requirement_display, 'compact') || requirementLabel(code);
      return stateFromTiming ? `${name} — ${stateFromTiming}` : `${name} — needs review`;
    }
    const d = String(task.description || '').trim();
    if (d.length > 12) return d.length > 160 ? `${d.slice(0, 157)}…` : d;
    return 'Potential issue — needs review';
  }

  if (task.source_type === 'issue') {
    const d = String(task.description || '').trim();
    if (d.length > 12) return d.length > 160 ? `${d.slice(0, 157)}…` : d;
  }

  return base;
}

function actionLabel(act) {
  const m = {
    snooze: 'Today item snoozed',
    dismiss: 'Today item hidden from Today',
    done: 'Today inbox marked done (legacy)',
    reviewed: 'Today item marked reviewed in Today only',
    restore: 'Today item restored to Today',
  };
  if (m[act]) return m[act];
  if (act == null || act === '') return '—';
  return inboxTimelineActionLabel(act);
}

function primaryClickBusinessOutcome(task) {
  const t = task?.primary_action_type;
  if (t === 'guided_evidence_resolution') return 'guided_evidence_opened';
  if (t === 'upload_evidence') return 'document_flow_opened';
  if (t === 'risk_follow_up') return 'risk_signal_review_opened';
  if (t === 'work_order') return 'work_order_detail_opened';
  if (t === 'issue') return 'maintenance_issue_opened';
  if (t === 'review_approval') return 'approval_opened';
  return 'primary_navigation';
}

/** Payload for Today analytics (snake_case keys; server sanitizes). */
function todayTaskAnalyticsProps(task) {
  if (!task) return {};
  const meta = task.metadata || {};
  const wo =
    meta.work_order_id ||
    meta.related_work_order_id ||
    (task.source_entity_type === 'work_order' ? task.source_entity_id : undefined);
  const out = {
    task_id: task.id,
    task_type: task.source_type || undefined,
  };
  if (task.property_id) out.property_id = task.property_id;
  if (wo) out.work_order_id = String(wo);
  return out;
}

function TaskCard({
  task,
  onRiskAction,
  riskLoading,
  showRiskInline,
  onOpenDismissModal,
  onPrimaryNavigate,
  onRunBusinessAction,
  onVisibilityTap,
  onOpenRequirementIntel,
  overrideBusy,
  complianceBookingBusyId,
  showComplianceBooking,
  enableTriage,
  inboxRequirementById,
}) {
  const navigate = useNavigate();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [visibilityOpen, setVisibilityOpen] = useState(false);
  const meta = task.metadata || {};
  const sid = meta.related_risk_signal_id;
  const busy = overrideBusy === task.id;
  const bookingBusy = complianceBookingBusyId === task.id;
  const shaped = shapeTodayBusinessActions(task, task.business_actions, showComplianceBooking);
  const workflow = shaped.workflow;
  const complianceUi = workflow === 'compliance';
  const mergedComplianceRow =
    complianceUi && inboxRequirementById instanceof Map
      ? buildRequirementShapedRowFromPriorityTask(task, inboxRequirementById)
      : null;
  const complianceResolved = mergedComplianceRow
    ? projectResolvedRequirementSemantics(mergedComplianceRow, { pagePropertyId: task.property_id })
    : null;
  const ordered = dedupeActionsByPrimaryPath(shaped.ordered);
  const primaryAct = ordered[0];
  const maxSecondarySlots = workflow === 'issue_risk' && showRiskInline && sid ? 1 : 2;
  let secondaryActs = ordered.slice(1, 1 + maxSecondarySlots);
  if (complianceUi) {
    const primaryId = primaryAct ? String(primaryAct.id) : '';
    const secondaryCandidate = ordered.find(
      (a) =>
        a !== primaryAct &&
        (String(a.id) === 'take_action_secondary' ||
          String(a.id) === 'view_requirement' ||
          String(a.intent) === 'view_requirement'),
    );
    secondaryActs =
      secondaryCandidate && String(secondaryCandidate.id) !== primaryId ? [secondaryCandidate] : [];
  }
  const riskStartInline =
    workflow === 'issue_risk' && showRiskInline && sid && secondaryActs.length < maxSecondarySlots;
  const riskStartInMoreOnly =
    workflow === 'issue_risk' && showRiskInline && sid && secondaryActs.length >= maxSecondarySlots;
  let displayTitle = todayDecisionLayerTitle(task);
  if (String(task?.source_type || '').toLowerCase() === 'work_order') {
    displayTitle = stripTechnicalParenTail(displayTitle);
  }
  const titleNorm = String(displayTitle || '').replace(/\s+/g, ' ').trim();
  const descRaw = String(task.description || '').trim();
  const descNorm = descRaw.replace(/\s+/g, ' ').trim();
  const showDescription = Boolean(descRaw && descNorm && descNorm !== titleNorm);
  const requirementWhyLine = complianceUi ? todayRequirementWhyItMattersLine(task) : null;
  const confidenceLine =
    !complianceUi && shouldShowTodayTaskConfidence(task) ? todayTaskConfidenceLine(task) : null;
  const guidedDetails = useMemo(() => todayTaskOperationalGuidance(task), [task]);
  const detailWhyLine = guidedDetails?.whyMatters || task.why_matters;
  const detailWhatLine = guidedDetails?.whatToDo || task.recommended_action;
  const hasLongContext = Boolean(detailWhyLine || detailWhatLine);
  const hasVisibilityActions = enableTriage && (task.visibility_actions || []).length > 0;
  const hasMoreOptionsBlock =
    hasVisibilityActions || (workflow === 'issue_risk' && showRiskInline && sid);
  const sourceAttributionLine = !complianceUi ? todayTaskSourceAttributionLine(task) : null;
  const primaryCtaResolved = resolveTaskCta(task, 'primary');
  const primaryWorkspacePath = resolveClientPortalPath(primaryCtaResolved.route, '/today');
  const jobDetailPath = /^\/operations\/jobs\/[^/]+/.test(String(primaryWorkspacePath || '').split('?')[0]);
  const continueWorkspaceLabel = jobDetailPath
    ? clientInboxJobCtaLabel(task) || CLIENT_INBOX_JOB_FALLBACK_CTA
    : continueWorkspaceCtaLabel(primaryWorkspacePath);
  const primaryBtnPath = primaryAct ? businessActionNavigatePath(primaryAct) : '';
  const primaryPathNorm = String(primaryBtnPath || '')
    .replace(/^https?:\/\/[^/]+/i, '')
    .split('?')[0];
  const primaryTargetsDocumentsUpload =
    (primaryAct && String(primaryAct.id) === 'upload_certificate') || primaryPathNorm === '/documents';
  const suppressContinueInDocuments =
    complianceUi &&
    String(continueWorkspaceLabel || '').toLowerCase() === 'continue in documents' &&
    (primaryTargetsDocumentsUpload || String(primaryWorkspacePath).split('?')[0] === '/documents');
  const primaryLabelForCompare = primaryAct
    ? labelForTodayBusinessAction(primaryAct, task, workflow)
    : sanitizeTodayCtaLabel(task.primary_action_label, task);
  const continueDuplicatesPrimary =
    Boolean(continueWorkspaceLabel) &&
    String(continueWorkspaceLabel).trim().toLowerCase() === String(primaryLabelForCompare).trim().toLowerCase();
  const continueDuplicatesRoute =
    Boolean(primaryBtnPath) &&
    Boolean(continueWorkspaceLabel) &&
    primaryBtnPath === primaryWorkspacePath &&
    primaryBtnPath !== '';
  const secondaryWorkspacePath =
    task.secondary_action_url && isSafeClientPortalPath(task.secondary_action_url)
      ? resolveClientPortalPath(task.secondary_action_url, '')
      : null;
  const secondaryMatchesPrimaryWorkspace =
    secondaryWorkspacePath != null && secondaryWorkspacePath === primaryWorkspacePath;
  const ghostLabel = task.secondary_action_label
    ? sanitizeBusinessActionLabel(task.secondary_action_label)
    : '';
  const ghostDuplicatesPrimary =
    ghostLabel && String(ghostLabel).trim().toLowerCase() === String(primaryLabelForCompare).trim().toLowerCase();
  const ghostDuplicatesRoute =
    secondaryWorkspacePath != null &&
    (secondaryWorkspacePath === primaryWorkspacePath ||
      (primaryBtnPath && secondaryWorkspacePath === primaryBtnPath));
  const ghostDuplicatesDocumentsUpload =
    complianceUi &&
    primaryTargetsDocumentsUpload &&
    secondaryWorkspacePath != null &&
    String(secondaryWorkspacePath).split('?')[0] === '/documents';
  const showGhostSecondary =
    Boolean(task.secondary_action_url && task.secondary_action_label) &&
    !ghostDuplicatesPrimary &&
    !ghostDuplicatesRoute &&
    !ghostDuplicatesDocumentsUpload;
  const showContinueWorkspace =
    Boolean(continueWorkspaceLabel) &&
    primaryWorkspacePath !== '/today' &&
    !primaryWorkspacePath.startsWith('/dashboard') &&
    !secondaryMatchesPrimaryWorkspace &&
    !continueDuplicatesPrimary &&
    !continueDuplicatesRoute &&
    !suppressContinueInDocuments;
  return (
    <Card className="border border-gray-200 shadow-sm overflow-hidden">
      <CardContent className="p-4 client-portal-prose">
        <div className="flex flex-col gap-3 min-w-0">
          <div className="min-w-0 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="text-xs font-normal shrink-0">
                {todayTaskCategoryBadge(task)}
              </Badge>
              <TodayUrgencyRow urgency={task.urgency} urgencyLevel={task.urgency_level} timingLabel={meta.timing_label} />
            </div>
            <h3 className="font-semibold text-midnight-blue text-base leading-snug break-words">{displayTitle}</h3>
            {propertyLine ? (
              <p className="text-sm text-gray-600 break-words">{propertyLine}</p>
            ) : null}
            <ListCognitionChip entity={cognitionEntity || task} className="mt-1" />
            {showDescription && (
              <p className="text-sm text-gray-700 line-clamp-3 break-words">{task.description}</p>
            )}
            {requirementWhyLine ? (
              <p className="text-xs text-gray-600 leading-snug">
                <span className="font-medium text-gray-800">Why it matters:</span> {requirementWhyLine}
              </p>
            ) : null}
            {complianceUi &&
            meta.evidence_completeness?.summary_label &&
            meta.evidence_completeness.summary_label !== 'Complete' ? (
              <p className="text-xs text-amber-900/90 leading-snug" data-testid="today-evidence-completeness-subtitle">
                {combineEvidenceSummaryWithResolvedSubline(
                  meta.evidence_completeness.summary_label,
                  complianceResolved,
                  mergedComplianceRow?.status ?? meta.requirement_status ?? task.status,
                )}
              </p>
            ) : null}
            {complianceUi && inboxTaskLinkedRequirementId(task) && onOpenRequirementIntel ? (
              <button
                type="button"
                className="text-left text-xs font-medium text-electric-teal hover:underline py-1"
                onClick={() => onOpenRequirementIntel(task)}
                data-testid="today-open-requirement-intel"
              >
                Requirement details
              </button>
            ) : null}
            {hasLongContext && (
              <button
                type="button"
                className="text-left text-xs font-medium text-electric-teal hover:underline py-1 min-h-[44px] sm:min-h-0 flex items-center"
                onClick={() => setDetailsOpen((o) => !o)}
                aria-expanded={detailsOpen}
              >
                {detailsOpen ? 'Hide details' : 'Show details'}
              </button>
            )}
            {detailsOpen && hasLongContext && (
              <div className="rounded-lg bg-gray-50 border border-gray-100 p-3 text-xs text-gray-600 space-y-2 break-words">
                {detailWhyLine ? (
                  <p>
                    <span className="font-medium text-gray-800">Why it matters:</span> {detailWhyLine}
                  </p>
                ) : null}
                {detailWhatLine ? (
                  <p>
                    <span className="font-medium text-gray-800">What to do:</span> {detailWhatLine}
                  </p>
                ) : null}
              </div>
            )}
            {task.freshness_timestamp && (
              <p className="text-xs text-gray-400">Updated {formatWhen(task.freshness_timestamp)}</p>
            )}
          </div>

          <div className="flex flex-col gap-2 pt-2 border-t border-gray-100 min-w-0">
            {confidenceLine ? (
              <p className="text-xs text-gray-600 leading-snug -mt-0.5">{confidenceLine}</p>
            ) : null}
            {sourceAttributionLine ? (
              <p className="text-[11px] font-medium text-midnight-blue/70 tracking-wide">{sourceAttributionLine}</p>
            ) : null}
            {primaryAct ? (
              <Button
                type="button"
                className="w-full min-h-12 h-12 text-sm font-semibold justify-center bg-midnight-blue hover:bg-midnight-blue/90 shadow-md ring-2 ring-electric-teal/40 ring-offset-2 ring-offset-white"
                disabled={bookingBusy}
                onClick={() => onRunBusinessAction(primaryAct, task)}
              >
                {bookingBusy && primaryAct.id === 'create_compliance_work_order' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  labelForTodayBusinessAction(primaryAct, task, workflow)
                )}
              </Button>
            ) : (
              <Button
                className="w-full min-h-12 h-12 text-sm font-semibold justify-center bg-midnight-blue hover:bg-midnight-blue/90 shadow-md ring-2 ring-electric-teal/40 ring-offset-2 ring-offset-white"
                disabled={bookingBusy}
                onClick={() => onPrimaryNavigate(task)}
              >
                {sanitizeTodayCtaLabel(task.primary_action_label, task)}
              </Button>
            )}
            {secondaryActs.length > 0 ? (
              <div className="flex flex-col gap-2">
                {secondaryActs.map((act) => (
                  <Button
                    key={act.id}
                    type="button"
                    variant="outline"
                    className="w-full min-h-11 h-11 text-sm justify-center border-midnight-blue/25 text-midnight-blue/90"
                    disabled={bookingBusy}
                    onClick={() => onRunBusinessAction(act, task)}
                  >
                    {labelForTodayBusinessAction(act, task, workflow)}
                  </Button>
                ))}
              </div>
            ) : null}
            {riskStartInline ? (
              <Button
                type="button"
                variant="outline"
                className="w-full min-h-11 h-11 text-sm justify-center border-midnight-blue/25 text-midnight-blue/90"
                disabled={riskLoading === `wo:${sid}`}
                onClick={() => onRiskAction('work_order', sid, task)}
              >
                {riskLoading === `wo:${sid}` ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Start maintenance job'}
              </Button>
            ) : null}
            {showContinueWorkspace ? (
              <button
                type="button"
                className="w-full text-left text-xs font-medium text-electric-teal hover:underline py-1 min-h-10"
                onClick={() => navigate(primaryWorkspacePath)}
              >
                {continueWorkspaceLabel}
              </button>
            ) : null}
            {showGhostSecondary ? (
              <Button
                variant="ghost"
                className="w-full min-h-11 h-11 justify-center text-sm text-gray-600 hover:text-midnight-blue hover:bg-gray-50"
                onClick={() => onPrimaryNavigate(task, 'secondary')}
              >
                <span className="text-electric-teal">{ghostLabel}</span>
                <ExternalLink className="w-3.5 h-3.5 ml-1 shrink-0 text-electric-teal" />
              </Button>
            ) : null}
            {complianceUi &&
            Array.isArray(meta.take_action?.supporting_external_links) &&
            meta.take_action.supporting_external_links.length > 0 ? (
              <div className="flex flex-col gap-1 pt-1 border-t border-gray-100">
                <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">External resources</p>
                {meta.take_action.supporting_external_links.map((lnk) => (
                  <button
                    key={lnk.key || lnk.url}
                    type="button"
                    className="text-left text-xs text-electric-teal hover:underline py-1 min-h-10 break-words w-full inline-flex items-start gap-1"
                    onClick={() => window.open(String(lnk.url || ''), '_blank', 'noopener,noreferrer')}
                  >
                    <span className="text-left">{lnk.label}</span>
                    <ExternalLink className="w-3.5 h-3.5 shrink-0 mt-0.5 opacity-80" aria-hidden />
                  </button>
                ))}
              </div>
            ) : null}
            {hasMoreOptionsBlock && (
              <div className="pt-1">
                {hasVisibilityActions ? (
                  <p className="text-xs text-gray-500 leading-snug border-t border-gray-100 pt-2 mb-1">
                    These options only change what appears on Today. To resolve the work, use the main action on the card.
                  </p>
                ) : null}
                <button
                  type="button"
                  className="text-left text-xs font-medium text-gray-500 hover:text-midnight-blue hover:underline py-2 min-h-[44px] sm:min-h-0 w-full"
                  onClick={() => setVisibilityOpen((v) => !v)}
                  aria-expanded={visibilityOpen}
                >
                  {visibilityOpen ? 'Hide options' : 'More options'}
                </button>
                {visibilityOpen && (
                  <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50/50 p-3 space-y-2 mt-1">
                    {workflow === 'issue_risk' && showRiskInline && sid ? (
                      <div className="flex flex-col gap-2 pb-1 border-b border-gray-200/80">
                        <Button
                          type="button"
                          variant="outline"
                          className="h-11 text-xs justify-center w-full"
                          disabled={riskLoading === `issue:${sid}`}
                          onClick={() => onRiskAction('issue', sid, task)}
                        >
                          {riskLoading === `issue:${sid}` ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            'Log maintenance issue'
                          )}
                        </Button>
                        {riskStartInMoreOnly ? (
                          <Button
                            type="button"
                            variant="outline"
                            className="h-11 text-xs justify-center w-full"
                            disabled={riskLoading === `wo:${sid}`}
                            onClick={() => onRiskAction('work_order', sid, task)}
                          >
                            {riskLoading === `wo:${sid}` ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              'Start maintenance job'
                            )}
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                    {hasVisibilityActions ? (
                      <div className="flex flex-col gap-3">
                        {(task.visibility_actions || []).map((va) => {
                          const detail = typeof va.detail === 'string' ? va.detail : '';
                          if (va.id === 'dismiss') {
                            return (
                              <div key={va.id} className="space-y-1">
                                <Button
                                  type="button"
                                  variant="outline"
                                  className="h-11 text-xs justify-center w-full"
                                  disabled={busy}
                                  onClick={() => onOpenDismissModal(task)}
                                >
                                  <EyeOff className="w-3.5 h-3.5 mr-1 shrink-0" />
                                  {va.label}
                                </Button>
                                {detail ? (
                                  <p className="text-[11px] text-gray-500 leading-snug pl-0.5">{detail}</p>
                                ) : null}
                              </div>
                            );
                          }
                          const isSnooze = va.id === 'snooze_1' || va.id === 'snooze_7';
                          const days = va.snooze_days || (va.id === 'snooze_7' ? 7 : 1);
                          return (
                            <div key={va.id} className="space-y-1">
                              <Button
                                type="button"
                                variant="outline"
                                className="h-11 text-xs justify-center w-full"
                                disabled={busy}
                                onClick={() => onVisibilityTap(va, task, isSnooze ? days : undefined)}
                              >
                                {isSnooze ? <Bell className="w-3.5 h-3.5 mr-1 shrink-0" /> : null}
                                {va.id === 'mark_reviewed' ? <CheckCircle className="w-3.5 h-3.5 mr-1 shrink-0" /> : null}
                                {va.label}
                              </Button>
                              {detail ? (
                                <p className="text-[11px] text-gray-500 leading-snug pl-0.5">{detail}</p>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            )}
            {busy && (
              <div className="flex justify-center py-1">
                <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function HiddenTaskCard({ item, onRestore, busy }) {
  const ov = item.user_override;
  const kind =
    ov === 'dismiss'
      ? 'Hidden from Today (dismissed)'
      : ov === 'reviewed'
        ? 'Marked reviewed in Today only'
        : 'Hidden from Today (legacy Done)';
  return (
    <Card className="border border-gray-200 bg-gray-50/60 shadow-sm">
      <CardContent className="p-4 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <Badge variant="outline" className="text-xs mb-1">{kind}</Badge>
          <p className="font-medium text-midnight-blue text-sm">
            {inboxTitleForDisplay({ title: item.title, metadata: item.metadata || {} })}
          </p>
          {item.dismiss_reason ? (
            <p className="text-xs text-gray-600 mt-1 break-words">
              <span className="font-medium text-gray-700">Reason:</span> {item.dismiss_reason}
            </p>
          ) : null}
          <p className="text-xs text-gray-500 mt-1">Hidden {formatWhen(item.hidden_at) || '—'}</p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onRestore(item)}>
          <RotateCcw className="w-3 h-3 mr-1" />
          Show in Today again
        </Button>
      </CardContent>
    </Card>
  );
}

function SnoozedTaskCard({ task, onRestore, busy }) {
  return (
    <Card className="border border-amber-200 bg-amber-50/40 shadow-sm">
      <CardContent className="p-4 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-midnight-blue text-sm">
            {inboxTitleForDisplay(task)}
          </p>
          {task.property_label && <p className="text-xs text-gray-600">{task.property_label}</p>}
          <p className="text-xs text-amber-900 mt-1">
            Snoozed until {formatWhen(task.snoozed_until) || task.snoozed_until || '—'}
          </p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onRestore(task)}>
          <RotateCcw className="w-3 h-3 mr-1" />
          Show in Today again
        </Button>
      </CardContent>
    </Card>
  );
}

function SectionBlock({
  title,
  tasks,
  onRiskAction,
  riskLoading,
  showRiskInline,
  onOpenDismissModal,
  onPrimaryNavigate,
  onRunBusinessAction,
  onVisibilityTap,
  onOpenRequirementIntel,
  overrideBusy,
  complianceBookingBusyId,
  showComplianceBooking,
  emptyHint,
  enableTriage,
  inboxRequirementById,
  propertyById,
  defaultCollapsed = false,
  urgentShowMoreLimit = null,
}) {
  const [expanded, setExpanded] = useState(!defaultCollapsed);
  const [showAllUrgent, setShowAllUrgent] = useState(false);

  if (!tasks?.length) {
    return (
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">{title}</h2>
        <p className="text-sm text-gray-500">{emptyHint}</p>
      </div>
    );
  }

  const capped =
    urgentShowMoreLimit != null && !showAllUrgent ? tasks.slice(0, urgentShowMoreLimit) : tasks;
  const hasMoreUrgent =
    urgentShowMoreLimit != null && tasks.length > urgentShowMoreLimit && !showAllUrgent;

  const header = (
    <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
      <h2 className="text-lg font-semibold text-gray-900">
        {title}{' '}
        <span className="text-sm font-normal text-gray-500">({tasks.length})</span>
      </h2>
      {defaultCollapsed ? (
        <button
          type="button"
          className="text-sm font-medium text-electric-teal hover:underline min-h-10 sm:min-h-0"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
        >
          {expanded ? 'Hide' : 'Show'}
        </button>
      ) : null}
    </div>
  );

  return (
    <div className="mb-8">
      {header}
      {(!defaultCollapsed || expanded) && (
        <>
          <div className="space-y-3">
            {capped.map((t) => (
              <TaskCard
                key={t.id}
                task={t}
                onRiskAction={onRiskAction}
                riskLoading={riskLoading}
                showRiskInline={showRiskInline}
                onOpenDismissModal={onOpenDismissModal}
                onPrimaryNavigate={onPrimaryNavigate}
                onRunBusinessAction={onRunBusinessAction}
                onVisibilityTap={onVisibilityTap}
                onOpenRequirementIntel={onOpenRequirementIntel}
                overrideBusy={overrideBusy}
                complianceBookingBusyId={complianceBookingBusyId}
                showComplianceBooking={showComplianceBooking}
                enableTriage={enableTriage}
                inboxRequirementById={inboxRequirementById}
                propertyById={propertyById}
              />
            ))}
          </div>
          {hasMoreUrgent ? (
            <button
              type="button"
              className="mt-3 text-sm font-medium text-electric-teal hover:underline min-h-11 w-full text-left sm:w-auto"
              onClick={() => setShowAllUrgent(true)}
            >
              Show more ({tasks.length - urgentShowMoreLimit} more)
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}

export default function ClientTasksPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { openGuidedEvidence } = useGuidedEvidenceModal();
  const { hasFeature } = useEntitlements();
  const [loading, setLoading] = useState(true);
  const [inboxEnrichmentLoading, setInboxEnrichmentLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);
  const [filter, setFilter] = useState('all');
  const [riskLoading, setRiskLoading] = useState(null);
  const [overrideBusyId, setOverrideBusyId] = useState(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const [propertyFilter, setPropertyFilter] = useState('');
  const [propertyOptions, setPropertyOptions] = useState([]);
  const [dismissModalTask, setDismissModalTask] = useState(null);
  const [dismissReason, setDismissReason] = useState('');
  const [complianceBookingBusyId, setComplianceBookingBusyId] = useState(null);
  const [planJobGate, setPlanJobGate] = useState(null);
  /** Same GET /client/requirements list as Requirements / Operating — aligns inbox with tracked rows. */
  const [portalRequirementsForInbox, setPortalRequirementsForInbox] = useState([]);
  /** From GET /client/command-center (same scoping as Dashboard when property_id is set). */
  const [jurisdictionComplianceNotice, setJurisdictionComplianceNotice] = useState(null);
  const [commandCenterFallbackAcknowledged, setCommandCenterFallbackAcknowledged] = useState(null);
  const [commandCenterDepth, setCommandCenterDepth] = useState(null);

  const isClientUser = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;

  useEffect(() => {
    if (!isClientUser) return;
    clientAPI
      .getComplianceSummary()
      .then((res) => setPropertyOptions(res.data?.properties || []))
      .catch(() => setPropertyOptions([]));
  }, [isClientUser]);

  const emitTodayAnalytics = useCallback((event, properties = {}) => {
    clientAPI
      .postAnalyticsEvent({ event, path: '/today', properties: { ...properties, page: 'today' } })
      .catch(() => {});
  }, []);

  const load = useCallback(() => {
    if (!isClientUser) return;
    emitTodayAnalytics('TODAY_PAGE_REQUESTED', {
      ...(propertyFilter ? { property_id: propertyFilter } : {}),
    });
    setLoading(true);
    setError('');
    const params = propertyFilter ? { property_id: propertyFilter } : {};
    setJurisdictionComplianceNotice(null);
    setCommandCenterFallbackAcknowledged(null);
    const todayKey = `${OPERATIONAL_CACHE_KEYS.todayItems}:${propertyFilter || 'all'}`;
    const reqKey = OPERATIONAL_CACHE_KEYS.requirementsOperational;
    Promise.all([
      fetchOperational(todayKey, () => clientAPI.getTodayItems(params).then((r) => r.data)),
      fetchOperational(reqKey, () =>
        clientAPI.getRequirements({ projection: 'full' }).then((r) => r.data).catch(() => ({ requirements: [] })),
      ),
      fetchOperational(`${OPERATIONAL_CACHE_KEYS.commandCenter}:all`, () =>
        clientAPI.getCommandCenter(params).then((r) => r.data).catch(() => null),
      ),
    ])
      .then(([todayHit, reqHit, ccHit]) => {
        setPayload(todayHit?.data ?? null);
        const reqs = reqHit?.data?.requirements;
        setPortalRequirementsForInbox(Array.isArray(reqs) ? reqs : []);
        const cc = ccHit?.data;
        setCommandCenterDepth(
          cc
            ? {
                urgent: cc.tasks_digest_summary?.urgent_count ?? cc.urgent_actions?.length ?? 0,
                primary: cc.primary_actions?.length ?? cc.urgent_actions?.length ?? 0,
              }
            : null,
        );
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load tasks');
        setPayload(null);
        emitTodayAnalytics('TODAY_PAGE_LOAD_FAILED', {
          ...(propertyFilter ? { property_id: propertyFilter } : {}),
          ...(typeof err?.response?.status === 'number' ? { http_status: err.response.status } : {}),
        });
      })
      .finally(() => setLoading(false));
    fetchOperational(OPERATIONAL_CACHE_KEYS.complianceSummary, () =>
      clientAPI.getComplianceSummary().then((r) => r.data),
    )
      .then((hit) => {
        const data = hit?.data;
        const notice = data?.jurisdiction_compliance_notice;
        setJurisdictionComplianceNotice(notice && typeof notice === 'object' ? notice : null);
        setCommandCenterFallbackAcknowledged(
          typeof data?.jurisdiction_fallback_acknowledged === 'boolean'
            ? data.jurisdiction_fallback_acknowledged
            : null,
        );
      })
      .catch(() => {});
  }, [isClientUser, propertyFilter, emitTodayAnalytics]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!isClientUser || loading || error || payload == null) return;
    emitTodayAnalytics('TODAY_PAGE_VIEWED', {
      ...(propertyFilter ? { property_id: propertyFilter } : {}),
    });
  }, [isClientUser, loading, error, payload, propertyFilter, emitTodayAnalytics]);

  // Keep Today inbox aligned with real-time Action -> Outcome events.
  useEffect(() => {
    if (!isClientUser) return undefined;
    const onOutcome = (evt) => {
      const outcomePropertyId = evt?.detail?.property_id;
      if (propertyFilter && outcomePropertyId && outcomePropertyId !== propertyFilter) return;
      load();
    };
    window.addEventListener('compliance-outcome', onOutcome);
    return () => window.removeEventListener('compliance-outcome', onOutcome);
  }, [isClientUser, propertyFilter, load]);

  const filterTask = useCallback(
    (t) => {
      if (filter === 'all') return true;
      const tags = t.filter_tags || [];
      if (filter === 'overdue') return (t.overdue_days ?? 0) > 0 || tags.includes('overdue');
      if (filter === 'compliance') return tags.includes('compliance');
      if (filter === 'operations') return tags.includes('operations');
      if (filter === 'approvals') return tags.includes('approvals');
      if (filter === 'billing') return tags.includes('billing');
      if (filter === 'risks') return tags.includes('risks');
      return true;
    },
    [filter]
  );

  const applyFilter = useCallback(
    (list) => (list || []).filter(filterTask),
    [filterTask],
  );

  const inboxRequirementById = useMemo(
    () => requirementMapFromList(portalRequirementsForInbox),
    [portalRequirementsForInbox],
  );

  const propertyById = useMemo(() => buildPropertyByIdMap(propertyOptions), [propertyOptions]);

  const [requirementIntelModal, setRequirementIntelModal] = useState(null);

  const openRequirementIntelFromTodayTask = useCallback(
    (task) => {
      const rid = inboxTaskLinkedRequirementId(task);
      if (!rid) return;
      const meta = task.metadata || {};
      const rd = meta.requirement_display;
      const seed =
        inboxRequirementById.get(String(rid)) ||
        ({
          requirement_id: String(rid),
          property_id: task.property_id,
          display_label:
            requirementDisplayTitle(rd, 'detail') ||
            requirementDisplayTitle(rd, 'compact') ||
            task.title,
        });
      setRequirementIntelModal({
        requirementId: String(rid),
        seed,
        propertyLabel: task.property_label || null,
      });
    },
    [inboxRequirementById],
  );

  const sections = useMemo(
    () => alignTodayPayloadTaskSections(payload, inboxRequirementById),
    [payload, inboxRequirementById],
  );

  const operationalSections = useMemo(
    () => buildOperationalSections(sections, applyFilter, inboxRequirementById),
    [sections, applyFilter, inboxRequirementById],
  );

  const allOpenTasks = useMemo(
    () => [...(sections.urgent || []), ...(sections.upcoming || []), ...(sections.in_progress || [])],
    [sections],
  );

  const primaryExecutionTask = useMemo(
    () => pickPrimaryExecutionTask(applyFilter(allOpenTasks), inboxRequirementById, propertyById),
    [allOpenTasks, applyFilter, inboxRequirementById, propertyById],
  );

  const primaryExecutionId = primaryExecutionTask?.id;

  const needsActionNow = useMemo(
    () => operationalSections.needsActionNow.filter((t) => t.id !== primaryExecutionId),
    [operationalSections.needsActionNow, primaryExecutionId],
  );

  const falseEmptyDisclosure = useMemo(
    () =>
      buildFalseEmptyStateDisclosure({
        visibleOpenCount:
          visibleOpenCount(operationalSections) + (primaryExecutionTask ? 1 : 0),
        bucketContinuation: payload?.bucket_continuation,
        commandCenterUrgentCount: commandCenterDepth?.urgent,
        commandCenterPrimaryCount: commandCenterDepth?.primary,
        propertyFilter,
      }),
    [operationalSections, primaryExecutionTask, payload, commandCenterDepth, propertyFilter],
  );

  const snoozed = applyFilter(sections.snoozed || []);
  const recent = applyFilter(sections.recently_completed);
  const waitingOnOthers = operationalSections.waitingOnOthers;
  const inProgress = operationalSections.inProgress;
  const hidden = sections.hidden || [];

  const summary = payload?.summary;
  const freshness = payload?.freshness;
  const spend = payload?.spend_this_month;

  const spendDisplay = useMemo(() => {
    if (!hasFeature('invoicing')) return null;
    if (!spend || spend.has_any_invoices === false) return null;
    return {
      amount: formatMoney(spend.total_amount, spend.currency),
      hint: spend.calculation_summary,
      count: spend.invoice_count,
    };
  }, [spend, hasFeature]);

  const jurisdictionTodayBanner = useMemo(
    () =>
      portfolioJurisdictionBannerState(jurisdictionComplianceNotice, commandCenterFallbackAcknowledged),
    [jurisdictionComplianceNotice, commandCenterFallbackAcknowledged],
  );

  const showRiskInline = hasFeature('predictive_maintenance') && hasFeature('maintenance_workflows');
  const showComplianceBooking =
    hasFeature('compliance_engine') && hasFeature('maintenance_workflows');

  const runBusinessAction = async (act, task) => {
    if (act?.id && task) {
      emitTodayAnalytics('TODAY_PRIMARY_ACTION_TRIGGERED', {
        ...todayTaskAnalyticsProps(task),
        action_id: act.id,
      });
    }
    if (
      task &&
      (act?.kind === 'guided_evidence_resolution' ||
        act?.kind === 'direct_evidence_action' ||
        act?.intent === 'guided_evidence_resolution' ||
        act?.intent === 'direct_evidence_action')
    ) {
      const pid = act.property_id || task.property_id;
      const rid = act.requirement_id || task.metadata?.requirement_id;
      if (pid && rid) {
        openGuidedEvidence({
          propertyId: String(pid),
          requirementId: String(rid),
          onSubmitted: load,
          initialEvidenceMode: act.evidence_mode || undefined,
        });
        return;
      }
    }
    const tid = task?.id;
    if (act.id === 'create_compliance_work_order' && act.requirement_id) {
      setComplianceBookingBusyId(tid);
      try {
        const res = await clientAPI.createRequirementComplianceJob(act.requirement_id, {
          compliance_purpose: act.compliance_purpose || 'inspection',
          compliance_generated_from: act.compliance_generated_from || 'requirement',
        });
        const woId = res.data?.work_order?.work_order_id;
        emitTodayAnalytics('today_compliance_job_started', {
          task_id: tid,
          requirement_code: act.requirement_code,
          work_order_id: woId,
        });
        toast.success(
          'Inspection job started. Open it next to assign a contractor and complete booking, visit, and proof.',
        );
        const pid = act.property_id || task?.property_id;
        if (pid && typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('compliance-outcome', { detail: { property_id: pid } }));
        }
        if (woId) navigate(resolveClientPortalPath(`/operations/jobs/${encodeURIComponent(woId)}`, '/operations/jobs'));
        else navigate(resolveClientPortalPath('/operations/work-orders', '/operations/work-orders'));
        load();
      } catch (err) {
        if (
          openPlanRestrictedJobGate(err, setPlanJobGate, {
            propertyId: act.property_id || task?.property_id,
            requirementId: act.requirement_id,
          })
        ) {
          return;
        }
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : d?.message || 'Could not start compliance fix');
      } finally {
        setComplianceBookingBusyId(null);
      }
      return;
    }
    if (act.id === 'create_maintenance_job' && act.issue_id) {
      navigate(resolveClientPortalPath(`/operations/issues/${encodeURIComponent(act.issue_id)}`, '/operations/issues'));
      return;
    }
    if (act.navigate) {
      navigate(resolveClientPortalPath(act.navigate, '/today'));
      return;
    }
    await onPrimaryNavigate(task, 'primary', { skipPrimaryWorkflowAnalytics: true });
  };

  const runVisibilityTap = async (va, task, snoozeDays) => {
    const tid = task?.id || task?.task_id;
    if (!tid) return;
    if (va.id === 'mark_reviewed') {
      setOverrideBusyId(tid);
      try {
        await clientAPI.todayItemMarkReviewed(tid);
        // TODAY_TASK_COMPLETED = inbox mark-reviewed only, not domain/workflow completion.
        emitTodayAnalytics('TODAY_TASK_COMPLETED', todayTaskAnalyticsProps(task));
        toast.success(
          'Marked as reviewed in Today only. Requirements, jobs, issues, and documents are unchanged—use the card’s main action to complete real work.',
        );
        load();
      } catch (err) {
        toast.error(err?.response?.data?.detail || 'Could not update Today inbox');
      } finally {
        setOverrideBusyId(null);
      }
      return;
    }
    if (va.id === 'snooze_1' || va.id === 'snooze_7' || snoozeDays) {
      const days = Number(snoozeDays || va.snooze_days || 1);
      setOverrideBusyId(tid);
      try {
        await clientAPI.todayItemSnooze(tid, days);
        emitTodayAnalytics('TODAY_TASK_SNOOZED', { ...todayTaskAnalyticsProps(task), days });
        toast.success(
          `Hidden from Today for ${days} day${days !== 1 ? 's' : ''}. Due dates and portfolio records are unchanged.`,
        );
        load();
      } catch (err) {
        toast.error(err?.response?.data?.detail || 'Could not snooze this item in Today');
      } finally {
        setOverrideBusyId(null);
      }
    }
  };

  const onPrimaryNavigate = async (task, which = 'primary', opts = {}) => {
    const skipWorkflow = opts.skipPrimaryWorkflowAnalytics === true;
    if (which === 'primary' && !skipWorkflow) {
      emitTodayAnalytics('TODAY_PRIMARY_ACTION_TRIGGERED', {
        ...todayTaskAnalyticsProps(task),
        action_id: opts.primaryActionId || 'next_step_primary',
        business_outcome: primaryClickBusinessOutcome(task),
      });
    }
    const cta = resolveTaskCta(task, which);
    if (which === 'primary' && cta.guidedEvidence) {
      openGuidedEvidence({
        propertyId: cta.guidedEvidence.propertyId,
        requirementId: cta.guidedEvidence.requirementId,
        onSubmitted: load,
        initialEvidenceMode: cta.guidedEvidence.initialEvidenceMode || undefined,
      });
      return;
    }
    const url = cta.route || (which === 'secondary' ? '/today' : '/dashboard');
    if (which === 'secondary') {
      emitTodayAnalytics('today_secondary_nav_clicked', {
        task_id: task.id,
        source_type: task.source_type,
        source_entity_type: task.source_entity_type || task.source_type,
        action_context_type: task.action_context_type || task.primary_action_type,
        business_outcome: 'secondary_navigation',
      });
    }
    try {
      await clientAPI.recordTaskNavigationIntent({
        task_id: task.id,
        intent_kind: which === 'secondary' ? 'secondary' : 'primary',
        target_path: url || '',
        source_type: task.source_type,
        action_context_type: task.action_context_type || task.primary_action_type,
      });
    } catch {
      /* non-blocking */
    }
    navigate(resolveClientPortalPath(url, which === 'secondary' ? '/today' : '/dashboard'));
  };

  const onPrimaryExecutionClick = () => {
    const task = primaryExecutionTask;
    if (!task) return;
    const shaped = shapeTodayBusinessActions(task, task.business_actions, showComplianceBooking);
    const primaryAct = dedupeActionsByPrimaryPath(shaped.ordered)[0];
    if (primaryAct) {
      runBusinessAction(primaryAct, task);
      return;
    }
    onPrimaryNavigate(task);
  };

  const restoreTodayItem = async (taskOrItem) => {
    const tid = taskOrItem?.id || taskOrItem?.task_id;
    if (!tid) return;
    setOverrideBusyId(tid);
    try {
      await clientAPI.todayItemRestore(tid);
      emitTodayAnalytics('today_task_restored', { task_id: tid, source_type: taskOrItem.source_type });
      toast.success(
        'Item restored to Today. This only brings the card back—use the main action if work still needs doing.',
      );
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not restore');
    } finally {
      setOverrideBusyId(null);
    }
  };

  const openDismissModal = (task) => {
    setDismissReason('');
    setDismissModalTask(task);
  };

  const confirmDismissTask = async () => {
    const task = dismissModalTask;
    const tid = task?.id || task?.task_id;
    const reason = dismissReason.trim();
    if (!tid || reason.length < 3) {
      toast.error('Please enter a reason for audit (at least 3 characters).');
      return;
    }
    setDismissModalTask(null);
    setDismissReason('');
    setOverrideBusyId(tid);
    try {
      await clientAPI.todayItemDismiss(tid, reason);
      emitTodayAnalytics('TODAY_TASK_DISMISSED', todayTaskAnalyticsProps(task));
      toast.success(
        'Hidden from Today (reason saved for audit). Requirements, jobs, issues, documents, and approvals are unchanged.',
      );
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not hide this item from Today');
    } finally {
      setOverrideBusyId(null);
    }
  };

  const onRiskAction = async (kind, signalId, taskForAnalytics) => {
    if (!signalId) return;
    const key = `${kind}:${signalId}`;
    setRiskLoading(key);
    try {
      if (taskForAnalytics) {
        emitTodayAnalytics('TODAY_PRIMARY_ACTION_TRIGGERED', {
          ...todayTaskAnalyticsProps(taskForAnalytics),
          action_id: kind === 'issue' ? 'risk_follow_up_issue' : 'risk_follow_up_work_order',
        });
      }
      emitTodayAnalytics('today_risk_follow_up_started', {
        follow_up_kind: kind,
        risk_signal_id: signalId,
        business_outcome: kind === 'issue' ? 'maintenance_issue_created' : 'maintenance_work_order_created',
      });
      if (kind === 'issue') {
        await clientAPI.createIssueFromRiskSignal(signalId, {});
        toast.success(
          'Maintenance issue logged from the flagged signal. Open Issues to triage—this creates a trackable maintenance record.',
        );
        navigate('/operations/issues');
      } else {
        await clientAPI.createWorkOrderFromRiskSignal(signalId, {});
        toast.success(
          'Maintenance job started from the flagged signal. Open Jobs to schedule—execution updates this property’s queue.',
        );
        navigate('/operations/work-orders');
      }
      load();
      const pid = taskForAnalytics?.property_id;
      if (pid && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('compliance-outcome', { detail: { property_id: pid } }));
      }
    } catch (err) {
      if (
        kind !== 'issue' &&
        openPlanRestrictedJobGate(err, setPlanJobGate, { propertyId: taskForAnalytics?.property_id })
      ) {
        return;
      }
      toast.error(err?.response?.data?.detail || 'Action failed');
    } finally {
      setRiskLoading(null);
    }
  };

  if (!isClientUser) {
    return (
      <div className="p-6">
        <p className="text-gray-600">Today is available to client users only.</p>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto" data-testid="client-tasks-page">
      <div className="mb-6">
        <div className="flex items-center gap-2 text-midnight-blue mb-1">
          <LayoutList className="w-7 h-7" />
          <h1 className="text-2xl md:text-3xl font-bold">Today</h1>
        </div>
        <p className="text-gray-600 text-sm md:text-base">{WORKSPACE_TODAY_PRIMARY}</p>
        <p className="text-xs text-gray-500 mt-2 leading-relaxed">{WORKSPACE_TODAY_VS_DASHBOARD}</p>
        <p className="text-sm text-gray-600 mt-2">{TODAY_PAGE_CONFIDENCE_LINE}</p>
        <p className="text-xs text-gray-500 mt-2 leading-relaxed">
          <Link
            to={buildSafeQueryPath('/help', { article: HELP_ARTICLE_SLUG_INBOX_VISIBILITY_TODAY })}
            className="text-electric-teal hover:underline font-medium"
          >
            How inbox visibility works
          </Link>
          <span className="text-gray-400">
            {' '}
            — evidence and outcomes live in requirements, documents, jobs, and issues—not in Today visibility alone.
          </span>
        </p>
      </div>

      {jurisdictionTodayBanner.showFull && (
          <Alert
            className="mb-4 border-amber-300 bg-amber-50/95 text-amber-950"
            data-testid="jurisdiction-fallback-today-alert"
          >
            <AlertCircle className="h-4 w-4 text-amber-800" />
            <AlertDescription>
              <p className="font-semibold text-amber-950">{JURISDICTION_FALLBACK_ALERT_TITLE}</p>
              <p className="text-sm mt-1.5 text-amber-950/95">{JURISDICTION_FALLBACK_ALERT_BODY}</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3 border-amber-400 bg-white hover:bg-amber-100"
                onClick={() => navigate('/settings/jurisdiction')}
              >
                {JURISDICTION_FALLBACK_CTA}
              </Button>
            </AlertDescription>
          </Alert>
        )}

      {jurisdictionTodayBanner.showCompact && (
        <Alert
          className="mb-4 border-amber-200/90 bg-amber-50/60 text-amber-950"
          data-testid="jurisdiction-fallback-today-reminder"
        >
          <Info className="h-4 w-4 text-amber-700 shrink-0" />
          <AlertDescription className="text-sm text-amber-950/95">
            <span>{JURISDICTION_PORTFOLIO_REMINDER_COMPACT} </span>
            <Link to="/settings/jurisdiction" className="font-medium text-electric-teal hover:underline">
              {JURISDICTION_FALLBACK_CTA}
            </Link>
          </AlertDescription>
        </Alert>
      )}

      {summary?.habit &&
        (summary.habit.urgent_open_total > 0 ||
          summary.habit.items_due_or_expiring_in_7_days > 0 ||
          (summary.habit.tasks_acknowledged_last_7_days ?? 0) > 0) && (
        <Alert className="mb-4 border-teal-200 bg-teal-50/80">
          <Info className="h-4 w-4 text-teal-700" />
          <AlertDescription className="text-teal-900 text-sm">
            {summary.habit.urgent_open_total > 0 && (
              <span className="block">
                You have <strong>{summary.habit.urgent_open_total}</strong> urgent item
                {summary.habit.urgent_open_total !== 1 ? 's' : ''} right now.
              </span>
            )}
            {summary.habit.items_due_or_expiring_in_7_days > 0 && (
              <span className="block mt-1">
                <strong>{summary.habit.items_due_or_expiring_in_7_days}</strong> open item
                {summary.habit.items_due_or_expiring_in_7_days !== 1 ? 's' : ''} with a due date in the next 7 days.
              </span>
            )}
            {(summary.habit.tasks_acknowledged_last_7_days ?? 0) > 0 && (
              <span className="block mt-1 text-teal-800">
                This week you cleared{' '}
                <strong>{summary.habit.tasks_acknowledged_last_7_days}</strong> inbox item
                {summary.habit.tasks_acknowledged_last_7_days !== 1 ? 's' : ''} (visibility only).
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}

      <Card className="mb-4 border-gray-200 bg-gray-50/50">
        <CardContent className="p-3 flex flex-wrap gap-3 text-sm">
          <div className="min-w-[5rem]">
            <span className="text-gray-500 text-xs">Needs action</span>
            <p className="text-lg font-bold text-midnight-blue tabular-nums">
              {(primaryExecutionTask ? 1 : 0) + needsActionNow.length}
            </p>
          </div>
          <div className="min-w-[5rem]">
            <span className="text-gray-500 text-xs">Waiting</span>
            <p className="text-lg font-bold text-midnight-blue tabular-nums">{waitingOnOthers.length}</p>
          </div>
          <div className="min-w-[5rem]">
            <span className="text-gray-500 text-xs">In progress</span>
            <p className="text-lg font-bold text-midnight-blue tabular-nums">{inProgress.length}</p>
          </div>
          <div className="min-w-[5rem]">
            <span className="text-gray-500 text-xs">Snoozed</span>
            <p className="text-lg font-bold text-midnight-blue tabular-nums">{snoozed.length}</p>
          </div>
          {falseEmptyDisclosure.continuationOverflow ? (
            <p className="text-xs text-gray-600 w-full border-t border-gray-200 pt-2">
              {falseEmptyDisclosure.continuationOverflow} more items prioritised in Command Centre — open there for the full queue.
            </p>
          ) : null}
        </CardContent>
      </Card>

      {falseEmptyDisclosure.isFalseCalm ? (
        <Alert className="mb-4 border-amber-300 bg-amber-50" data-testid="today-false-calm-notice">
          <AlertCircle className="h-4 w-4 text-amber-800" />
          <AlertDescription className="text-sm text-amber-950">
            {falseEmptyDisclosure.message}{' '}
            <Link to="/command-center" className="font-medium text-electric-teal hover:underline">
              Open Command Centre
            </Link>
          </AlertDescription>
        </Alert>
      ) : null}

      {filter !== 'all' && (
        <Alert className="mb-4 border-sky-200 bg-sky-50" data-testid="today-category-filter-notice">
          <AlertDescription className="text-sm text-sky-950">
            Category filter active — summary counts include all categories; section lists below show only{' '}
            <strong>{FILTER_CHIPS.find((c) => c.id === filter)?.label || filter}</strong> items.
          </AlertDescription>
        </Alert>
      )}

      {payload?.bucket_continuation && Object.keys(payload.bucket_continuation).length > 0 && (
        <Alert className="mb-4 border-gray-200 bg-gray-50" data-testid="today-bucket-continuation-notice">
          <AlertDescription className="text-sm text-gray-700">
            Some inbox rows are capped in this view. Open Command Center for the full prioritised queue.
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between mb-6">
        <div className="flex flex-wrap gap-2">
          {FILTER_CHIPS.map((c) => (
            <Button
              key={c.id}
              type="button"
              size="sm"
              variant={filter === c.id ? 'default' : 'outline'}
              className={`min-h-11 px-3 ${filter === c.id ? 'bg-midnight-blue' : ''}`}
              onClick={() => setFilter(c.id)}
            >
              {c.label}
            </Button>
          ))}
        </div>
        {propertyOptions.length > 0 && (
          <div className="flex flex-col gap-1 text-sm w-full sm:w-auto sm:min-w-[14rem]">
            <label htmlFor="tasks-property-filter" className="text-gray-600">
              Property
            </label>
            <select
              id="tasks-property-filter"
              value={propertyFilter}
              onChange={(e) => setPropertyFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-white w-full max-w-full min-h-11"
            >
              <option value="">All properties</option>
              {propertyOptions.map((p) => (
                <option key={p.property_id} value={p.property_id}>
                  {propertyOptionLabel(p)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && !payload ? (
        <PortalSectionSkeleton rows={6} />
      ) : null}

      <Dialog open={Boolean(dismissModalTask)} onOpenChange={(open) => !open && setDismissModalTask(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Hide from Today</DialogTitle>
            <DialogDescription className="sr-only">
              Visibility only: hides the card from Today until restored. Does not complete requirements, jobs, issues, or
              documents.
            </DialogDescription>
          </DialogHeader>
          <div className="text-left text-gray-600 text-sm space-y-2">
            <p>
              This removes the card from your open Today lists until you <strong>Show in Today again</strong> from Snoozed
              or Hidden. It is a visibility action only.
            </p>
            <p className="font-medium text-midnight-blue">It does not:</p>
            <ul className="list-disc pl-5 space-y-0.5 text-gray-600">
              <li>upload a document or satisfy a requirement</li>
              <li>close or progress a job</li>
              <li>resolve an issue</li>
              <li>approve an invoice</li>
              <li>change compliance scores or obligations</li>
            </ul>
            <p>Your reason is stored for audit and support (minimum 3 characters).</p>
          </div>
          <textarea
            className="w-full min-h-[100px] border border-gray-200 rounded-lg p-3 text-sm"
            placeholder="Reason for audit log (required, min. 3 characters)"
            value={dismissReason}
            onChange={(e) => setDismissReason(e.target.value)}
            aria-label="Reason for hiding from Today"
          />
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setDismissModalTask(null)}>
              Cancel
            </Button>
            <Button type="button" className="bg-midnight-blue hover:bg-midnight-blue/90" onClick={confirmDismissTask}>
              Hide from Today
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <RequirementIntelligenceModal
        open={!!requirementIntelModal}
        requirementId={requirementIntelModal?.requirementId || null}
        seedRequirement={requirementIntelModal?.seed || null}
        propertyLabel={requirementIntelModal?.propertyLabel || null}
        onClose={() => setRequirementIntelModal(null)}
        onNavigate={(path) => {
          setRequirementIntelModal(null);
          navigate(path);
        }}
      />
      <PlanRestrictedJobModal gate={planJobGate} onDismiss={() => setPlanJobGate(null)} />

      {!loading && !error && (
        <>
          {primaryExecutionTask ? (
            <TodayExecutionHero
              entity={primaryExecutionTask}
              task={primaryExecutionTask}
              onPrimaryClick={onPrimaryExecutionClick}
              primaryBusy={overrideBusyId === primaryExecutionTask.id || complianceBookingBusyId === primaryExecutionTask.id}
            />
          ) : falseEmptyDisclosure.genuinelyEmpty ? (
            <Alert className="mb-6 border-gray-200 bg-gray-50" data-testid="today-genuinely-empty">
              <AlertDescription className="text-sm text-gray-700">{falseEmptyDisclosure.message}</AlertDescription>
            </Alert>
          ) : null}

          <SectionBlock
            title="Needs action now"
            tasks={needsActionNow}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onOpenDismissModal={openDismissModal}
            onPrimaryNavigate={onPrimaryNavigate}
            onRunBusinessAction={runBusinessAction}
            onVisibilityTap={runVisibilityTap}
            onOpenRequirementIntel={openRequirementIntelFromTodayTask}
            overrideBusy={overrideBusyId}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage
            inboxRequirementById={inboxRequirementById}
            propertyById={propertyById}
            urgentShowMoreLimit={8}
            emptyHint={
              primaryExecutionTask
                ? 'No other immediate actions — your top next step is above.'
                : falseEmptyDisclosure.isFalseCalm
                  ? falseEmptyDisclosure.message
                  : 'No items need your action in this view right now.'
            }
          />
          <SectionBlock
            title="Waiting on others"
            tasks={waitingOnOthers}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onOpenDismissModal={openDismissModal}
            onPrimaryNavigate={onPrimaryNavigate}
            onRunBusinessAction={runBusinessAction}
            onVisibilityTap={runVisibilityTap}
            onOpenRequirementIntel={openRequirementIntelFromTodayTask}
            overrideBusy={overrideBusyId}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage
            inboxRequirementById={inboxRequirementById}
            propertyById={propertyById}
            defaultCollapsed={waitingOnOthers.length > 4}
            emptyHint="Nothing awaiting review, approval, or external follow-up."
          />
          <SectionBlock
            title="In progress"
            tasks={inProgress}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onOpenDismissModal={openDismissModal}
            onPrimaryNavigate={onPrimaryNavigate}
            onRunBusinessAction={runBusinessAction}
            onVisibilityTap={runVisibilityTap}
            onOpenRequirementIntel={openRequirementIntelFromTodayTask}
            overrideBusy={overrideBusyId}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage
            inboxRequirementById={inboxRequirementById}
            propertyById={propertyById}
            defaultCollapsed
            emptyHint="No active jobs or workflows in progress."
          />
          {snoozed.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Snoozed / deferred</h2>
              <p className="text-sm text-gray-500 mb-3">
                Hidden from Today until the date shown—portfolio records and due dates are unchanged. Use Show in Today again when
                you want the card back.
              </p>
              <div className="space-y-3">
                {snoozed.map((t) => (
                  <SnoozedTaskCard
                    key={t.id}
                    task={t}
                    busy={overrideBusyId === t.id}
                    onRestore={(tk) => restoreTodayItem(tk)}
                  />
                ))}
              </div>
            </div>
          )}
          {hidden.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Hidden from Today (dismissed, reviewed, legacy Done)</h2>
              <p className="text-sm text-gray-500 mb-3">
                Visibility only: these cards are off your open Today lists. Requirements, jobs, issues, documents, and scores are
                unchanged unless you completed work elsewhere—use Show in Today again to bring a card back.
              </p>
              <div className="space-y-3">
                {hidden.map((h) => (
                  <HiddenTaskCard
                    key={h.task_id}
                    item={h}
                    busy={overrideBusyId === h.task_id}
                    onRestore={(it) => restoreTodayItem(it)}
                  />
                ))}
              </div>
            </div>
          )}
          <SectionBlock
            title="Recently completed"
            tasks={recent}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onOpenDismissModal={openDismissModal}
            onPrimaryNavigate={onPrimaryNavigate}
            onRunBusinessAction={runBusinessAction}
            onVisibilityTap={runVisibilityTap}
            onOpenRequirementIntel={openRequirementIntelFromTodayTask}
            overrideBusy={overrideBusyId}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage={false}
            inboxRequirementById={inboxRequirementById}
            propertyById={propertyById}
            emptyHint="Recent requirement and invoice milestones will show here."
          />
          {payload?.activity_feed?.length > 0 && (
            <Card className="mb-8 border-gray-200">
              <CardHeader className="pb-2">
                <button
                  type="button"
                  className="flex items-center gap-2 text-left w-full"
                  onClick={() => setActivityOpen((o) => !o)}
                >
                  <History className="w-4 h-4 text-gray-600" />
                  <CardTitle className="text-base">Inbox activity</CardTitle>
                  <span className="text-xs text-gray-500 ml-auto">{activityOpen ? 'Hide' : 'Show'}</span>
                </button>
              </CardHeader>
              {activityOpen && (
                <CardContent className="pt-0">
                  <ul className="text-sm text-gray-700 space-y-2 border-t border-gray-100 pt-3">
                    {payload.activity_feed.map((row) => (
                      <li key={row.event_id || `${row.task_id}-${row.created_at}`} className="flex flex-wrap gap-x-2 gap-y-0.5">
                        <span className="font-medium text-midnight-blue">
                          {row.action_label || actionLabel(row.action)}
                        </span>
                        {row.task_title ? (
                          <span className="text-gray-600 text-xs truncate max-w-[16rem]" title={row.task_id || undefined}>
                            {row.task_title}
                          </span>
                        ) : null}
                        <span className="text-gray-400 text-xs">{formatWhen(row.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
