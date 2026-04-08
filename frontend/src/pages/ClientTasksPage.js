/**
 * Client portal — Today (priorities inbox). Aggregated server-side tasks with sections,
 * urgency, deep links, and selective inline actions (risk → issue / work order).
 *
 * Today model (keep aligned with docs/CLIENT_PORTAL_WORKFLOW_MATRIX.md and today_projection_service.py):
 *
 * - Business actions: server-provided `business_actions` (upload certificate → navigate to documents vault
 *   with focus=upload; create compliance job → POST requirement job then navigate; view requirement/issue/job;
 *   etc.). These drive real domain workflows, not inbox presentation alone.
 *
 * - Visibility actions: `visibility_actions` → POST /api/today/items/{id}/snooze | mark-reviewed | dismiss.
 *   Snooze/reviewed/dismiss only touch task overrides; they do not change compliance outcome on requirements.
 *
 * Analytics: `TODAY_TASK_COMPLETED` = inbox visibility only (mark reviewed), not underlying object resolved.
 * Workflow attempts: `TODAY_PRIMARY_ACTION_TRIGGERED` (see backend `product_analytics_service` module doc).
 *
 * - Restore: hidden/dismissed items expose restore → POST /api/today/items/{id}/restore (see restoreTodayItem).
 *   Clears overrides so the task can reappear; does not mutate underlying requirement/job/document state.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { inboxTitleForDisplay } from '../domain/presentDomain';
import { useNavigate, Link } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
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
import { toast } from 'sonner';
import { TodayUrgencyRow } from '../components/client/UrgencyDisplay';
import { resolveClientPortalPath } from '../utils/clientPortalNavigation';
import { portfolioJurisdictionBannerState } from '../utils/jurisdictionUiPolicy';
import { resolveTaskCta } from '../utils/ctaRegistry';
import {
  JURISDICTION_FALLBACK_ALERT_BODY,
  JURISDICTION_FALLBACK_ALERT_TITLE,
  JURISDICTION_FALLBACK_CTA,
  JURISDICTION_PORTFOLIO_REMINDER_COMPACT,
} from '../utils/jurisdictionComplianceCopy';

const FILTER_CHIPS = [
  { id: 'all', label: 'All' },
  { id: 'compliance', label: 'Requirements' },
  { id: 'operations', label: 'Operations' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'billing', label: 'Billing' },
  { id: 'risks', label: 'Risk signals' },
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
  const map = {
    requirement: 'Requirement',
    risk_signal: 'Risk signal',
    work_order: 'Work order',
    approval: 'Approval',
    issue: 'Maintenance issue',
    priority_action: 'Action',
  };
  return map[st] || st || 'Task';
}

function actionLabel(act) {
  const m = {
    snooze: 'Snoozed',
    dismiss: 'Dismissed task',
    done: 'Marked done (legacy)',
    reviewed: 'Marked reviewed',
    restore: 'Restored',
  };
  return m[act] || act || '—';
}

function primaryClickBusinessOutcome(task) {
  const t = task?.primary_action_type;
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
  onTaskTitleClick,
  overrideBusy,
  complianceBookingBusyId,
  showComplianceBooking,
  enableTriage,
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const meta = task.metadata || {};
  const sid = meta.related_risk_signal_id;
  const busy = overrideBusy === task.id;
  const ce = meta.compliance_execution_booking;
  const bookingBusy = complianceBookingBusyId === task.id;
  const businessActions = task.business_actions || [];
  const hasComplianceCreateAction = businessActions.some((a) => a.id === 'create_compliance_work_order');
  const displayTitle = inboxTitleForDisplay(task);
  const hasLongContext = Boolean(task.why_matters || task.recommended_action);
  const entityHint =
    task.source_entity_type && task.source_entity_id
      ? `${task.source_entity_type.replace(/_/g, ' ')} · ${String(task.source_entity_id).slice(0, 12)}${String(task.source_entity_id).length > 12 ? '…' : ''}`
      : null;

  return (
    <Card className="border border-gray-200 shadow-sm overflow-hidden">
      <CardContent className="p-4 client-portal-prose">
        <div className="flex flex-col gap-4 min-w-0">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="text-xs font-normal shrink-0">
                {sourceTypeLabel(task.source_type)}
              </Badge>
              <TodayUrgencyRow urgency={task.urgency} urgencyLevel={task.urgency_level} timingLabel={meta.timing_label} />
            </div>
            <h3
              className={`font-semibold text-midnight-blue text-base leading-snug break-words${onTaskTitleClick ? ' cursor-pointer hover:underline decoration-midnight-blue/30' : ''}`}
              role={onTaskTitleClick ? 'button' : undefined}
              tabIndex={onTaskTitleClick ? 0 : undefined}
              onClick={() => onTaskTitleClick?.(task)}
              onKeyDown={(e) => {
                if (!onTaskTitleClick) return;
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onTaskTitleClick(task);
                }
              }}
            >
              {displayTitle}
            </h3>
            {entityHint && (
              <p className="text-[11px] text-gray-400 font-mono break-all" title={task.source_entity_id}>
                Linked: {entityHint}
              </p>
            )}
            {task.property_label && (
              <p className="text-sm text-gray-600 break-words">{task.property_label}</p>
            )}
            {task.description && (
              <p className="text-sm text-gray-700 line-clamp-3 break-words">{task.description}</p>
            )}
            {hasLongContext && (
              <button
                type="button"
                className="text-left text-xs font-medium text-electric-teal hover:underline py-1 min-h-[44px] sm:min-h-0 flex items-center"
                onClick={() => setDetailsOpen((o) => !o)}
                aria-expanded={detailsOpen}
              >
                {detailsOpen ? 'Hide details' : 'What’s wrong, why it matters, what to do'}
              </button>
            )}
            {detailsOpen && hasLongContext && (
              <div className="rounded-lg bg-gray-50 border border-gray-100 p-3 text-xs text-gray-600 space-y-2 break-words">
                {task.why_matters && (
                  <p>
                    <span className="font-medium text-gray-800">Why it matters:</span> {task.why_matters}
                  </p>
                )}
                {task.recommended_action && (
                  <p>
                    <span className="font-medium text-gray-800">What to do:</span> {task.recommended_action}
                  </p>
                )}
              </div>
            )}
            {task.freshness_timestamp && (
              <p className="text-xs text-gray-400">Updated {formatWhen(task.freshness_timestamp)}</p>
            )}
          </div>

          <div className="flex flex-col gap-3 pt-2 border-t border-gray-100 min-w-0">
            {businessActions.length > 0 ? (
              <div>
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Business actions</p>
                <div className="flex flex-col gap-2">
                  {businessActions.map((act) => {
                    const isPrimary = act.primary === true || act.id === 'open_primary';
                    return (
                      <Button
                        key={act.id}
                        type="button"
                        variant={isPrimary ? 'default' : 'outline'}
                        className={`w-full min-h-11 h-11 text-sm justify-center ${
                          isPrimary
                            ? 'bg-midnight-blue hover:bg-midnight-blue/90 shadow-md ring-2 ring-electric-teal/40 ring-offset-2 ring-offset-white'
                            : 'border-midnight-blue/20'
                        }`}
                        disabled={bookingBusy}
                        onClick={() => onRunBusinessAction(act, task)}
                      >
                        {act.label}
                      </Button>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div>
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Next step</p>
                <Button
                  className="w-full min-h-12 h-12 text-sm font-semibold justify-center bg-midnight-blue hover:bg-midnight-blue/90 shadow-sm"
                  disabled={bookingBusy}
                  onClick={() => onPrimaryNavigate(task)}
                >
                  {task.primary_action_label || 'Open'}
                </Button>
              </div>
            )}
            {showComplianceBooking && ce?.eligible && !hasComplianceCreateAction && ce.linked_property_requirement_id && (
              <div>
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Compliance job
                </p>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full min-h-11 h-11 text-sm justify-center border-electric-teal text-electric-teal hover:bg-teal-50"
                  disabled={busy || bookingBusy}
                  onClick={() =>
                    onRunBusinessAction(
                      {
                        id: 'create_compliance_work_order',
                        requirement_id: ce.linked_property_requirement_id,
                        property_id: ce.property_id,
                        requirement_code: ce.requirement_code,
                        compliance_purpose: ce.compliance_purpose || 'inspection',
                        compliance_generated_from: ce.compliance_generated_from || 'requirement',
                      },
                      task
                    )
                  }
                >
                  {bookingBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create compliance job'}
                </Button>
                <p className="text-xs text-gray-500 mt-1.5 leading-snug">
                  Creates the job only. Open the job to assign a contractor and complete booking, execution, and proof.
                </p>
              </div>
            )}
            {showRiskInline && task.primary_action_type === 'risk_follow_up' && sid && (
              <div>
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Follow up on risk</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    className="min-h-11 h-11 w-full justify-center text-xs sm:text-sm"
                    disabled={riskLoading === `issue:${sid}`}
                    onClick={() => onRiskAction('issue', sid, task)}
                  >
                    {riskLoading === `issue:${sid}` ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Log maintenance issue'}
                  </Button>
                  <Button
                    variant="outline"
                    className="min-h-11 h-11 w-full justify-center text-xs sm:text-sm"
                    disabled={riskLoading === `wo:${sid}`}
                    onClick={() => onRiskAction('work_order', sid, task)}
                  >
                    {riskLoading === `wo:${sid}` ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Start maintenance job'}
                  </Button>
                </div>
              </div>
            )}
            {task.secondary_action_url && task.secondary_action_label && (
              <Button
                variant="ghost"
                className="w-full min-h-11 h-11 text-electric-teal justify-center text-sm"
                onClick={() => onPrimaryNavigate(task, 'secondary')}
              >
                {task.secondary_action_label}
                <ExternalLink className="w-3.5 h-3.5 ml-1 shrink-0" />
              </Button>
            )}
            {enableTriage && (task.visibility_actions || []).length > 0 && (
              <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50/50 p-3 space-y-2">
                <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Inbox visibility only
                </p>
                <p className="text-xs text-gray-500 leading-snug">
                  These actions change what you see here — not compliance outcomes, approvals, or job state.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {(task.visibility_actions || []).map((va) => {
                    if (va.id === 'dismiss') {
                      return (
                        <Button
                          key={va.id}
                          type="button"
                          variant="outline"
                          className="h-11 text-xs justify-center col-span-2 sm:col-span-1"
                          disabled={busy}
                          title="Requires a reason; logged and audited"
                          onClick={() => onOpenDismissModal(task)}
                        >
                          <EyeOff className="w-3.5 h-3.5 mr-1 shrink-0" />
                          {va.label}
                        </Button>
                      );
                    }
                    const isSnooze = va.id === 'snooze_1' || va.id === 'snooze_7';
                    const days = va.snooze_days || (va.id === 'snooze_7' ? 7 : 1);
                    return (
                      <Button
                        key={va.id}
                        type="button"
                        variant="outline"
                        className="h-11 text-xs justify-center"
                        disabled={busy}
                        onClick={() => onVisibilityTap(va, task, isSnooze ? days : undefined)}
                      >
                        {isSnooze ? <Bell className="w-3.5 h-3.5 mr-1 shrink-0" /> : null}
                        {va.id === 'mark_reviewed' ? <CheckCircle className="w-3.5 h-3.5 mr-1 shrink-0" /> : null}
                        {va.label}
                      </Button>
                    );
                  })}
                </div>
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
    ov === 'dismiss' ? 'Dismissed task' : ov === 'reviewed' ? 'Marked reviewed' : 'Hidden (legacy Done)';
  return (
    <Card className="border border-gray-200 bg-gray-50/60 shadow-sm">
      <CardContent className="p-4 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <Badge variant="outline" className="text-xs mb-1">{kind}</Badge>
          <p className="font-medium text-midnight-blue text-sm">{item.title || item.task_id}</p>
          {item.dismiss_reason ? (
            <p className="text-xs text-gray-600 mt-1 break-words">
              <span className="font-medium text-gray-700">Reason:</span> {item.dismiss_reason}
            </p>
          ) : null}
          <p className="text-xs text-gray-500 mt-1">Hidden {formatWhen(item.hidden_at) || '—'}</p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onRestore(item)}>
          <RotateCcw className="w-3 h-3 mr-1" />
          Restore
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
          <p className="font-medium text-midnight-blue text-sm">{task.title}</p>
          {task.property_label && <p className="text-xs text-gray-600">{task.property_label}</p>}
          <p className="text-xs text-amber-900 mt-1">
            Snoozed until {formatWhen(task.snoozed_until) || task.snoozed_until || '—'}
          </p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onRestore(task)}>
          <RotateCcw className="w-3 h-3 mr-1" />
          Restore
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
  onTaskTitleClick,
  overrideBusy,
  complianceBookingBusyId,
  showComplianceBooking,
  emptyHint,
  enableTriage,
}) {
  if (!tasks?.length) {
    return (
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">{title}</h2>
        <p className="text-sm text-gray-500">{emptyHint}</p>
      </div>
    );
  }
  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">{title}</h2>
      <div className="space-y-3">
        {tasks.map((t) => (
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
            onTaskTitleClick={onTaskTitleClick}
            overrideBusy={overrideBusy}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage={enableTriage}
          />
        ))}
      </div>
    </div>
  );
}

export default function ClientTasksPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { hasFeature } = useEntitlements();
  const [loading, setLoading] = useState(true);
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
  /** From GET /client/command-center (same scoping as Dashboard when property_id is set). */
  const [jurisdictionComplianceNotice, setJurisdictionComplianceNotice] = useState(null);
  const [commandCenterFallbackAcknowledged, setCommandCenterFallbackAcknowledged] = useState(null);

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
    clientAPI
      .getCommandCenter(params)
      .then((res) => {
        const summary = res.data?.compliance_status_summary;
        const notice = summary?.jurisdiction_compliance_notice;
        setJurisdictionComplianceNotice(notice && typeof notice === 'object' ? notice : null);
        setCommandCenterFallbackAcknowledged(
          typeof summary?.jurisdiction_fallback_acknowledged === 'boolean'
            ? summary.jurisdiction_fallback_acknowledged
            : null,
        );
      })
      .catch(() => {
        /* Do not surface errors; Today does not depend on command-center. */
      });
    clientAPI
      .getTodayItems(params)
      .then((res) => setPayload(res.data))
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load tasks');
        setPayload(null);
        emitTodayAnalytics('TODAY_PAGE_LOAD_FAILED', {
          ...(propertyFilter ? { property_id: propertyFilter } : {}),
          ...(typeof err?.response?.status === 'number' ? { http_status: err.response.status } : {}),
        });
      })
      .finally(() => setLoading(false));
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

  const applyFilter = (list) => (list || []).filter(filterTask);

  const sections = payload?.tasks || {};
  const urgent = applyFilter(sections.urgent);
  const upcoming = applyFilter(sections.upcoming);
  const inProgress = applyFilter(sections.in_progress);
  const recent = applyFilter(sections.recently_completed);
  const snoozed = applyFilter(sections.snoozed || []);
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

  const onTaskTitleClick = useCallback(
    (task) => {
      emitTodayAnalytics('TODAY_TASK_CLICKED', todayTaskAnalyticsProps(task));
    },
    [emitTodayAnalytics]
  );

  const runBusinessAction = async (act, task) => {
    if (act?.id && task) {
      emitTodayAnalytics('TODAY_PRIMARY_ACTION_TRIGGERED', {
        ...todayTaskAnalyticsProps(task),
        action_id: act.id,
      });
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
        toast.success('Compliance job created.');
        if (woId) navigate(resolveClientPortalPath(`/operations/jobs/${encodeURIComponent(woId)}`, '/operations/jobs'));
        else navigate(resolveClientPortalPath('/operations/work-orders', '/operations/work-orders'));
        load();
      } catch (err) {
        toast.error(err?.response?.data?.detail || 'Could not create compliance job');
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
        toast.success('Marked reviewed in inbox');
        load();
      } catch (err) {
        toast.error(err?.response?.data?.detail || 'Could not update inbox');
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
        toast.success(`Snoozed ${days} day${days !== 1 ? 's' : ''}`);
        load();
      } catch (err) {
        toast.error(err?.response?.data?.detail || 'Could not snooze');
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

  const restoreTodayItem = async (taskOrItem) => {
    const tid = taskOrItem?.id || taskOrItem?.task_id;
    if (!tid) return;
    setOverrideBusyId(tid);
    try {
      await clientAPI.todayItemRestore(tid);
      emitTodayAnalytics('today_task_restored', { task_id: tid, source_type: taskOrItem.source_type });
      toast.success('Restored to inbox');
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
      toast.error('Please enter a reason (at least 3 characters).');
      return;
    }
    setDismissModalTask(null);
    setDismissReason('');
    setOverrideBusyId(tid);
    try {
      await clientAPI.todayItemDismiss(tid, reason);
      emitTodayAnalytics('TODAY_TASK_DISMISSED', todayTaskAnalyticsProps(task));
      toast.success('Task dismissed — obligation unchanged; action audited.');
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not dismiss task');
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
        toast.success('Maintenance issue logged from risk signal');
        navigate('/operations/issues');
      } else {
        await clientAPI.createWorkOrderFromRiskSignal(signalId, {});
        toast.success('Maintenance job started from risk signal');
        navigate('/operations/work-orders');
      }
      load();
    } catch (err) {
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
        <p className="text-gray-600 text-sm md:text-base">
          Command centre for your portfolio: each card links to a real requirement, job, approval, or risk signal.
          Primary actions move work forward; snooze and dismiss only change what you see here.
        </p>
        <p className="text-xs text-gray-500 mt-2 leading-relaxed">
          <Link
            to="/help?article=command-centre-tasks-inbox"
            className="text-electric-teal hover:underline font-medium"
          >
            How inbox visibility works
          </Link>
          <span className="text-gray-400">
            {' '}
            — satisfying compliance always requires evidence, verification, or the right workflow outcome — not “Mark reviewed”.
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
                This week you reviewed, dismissed, or legacy-marked-done{' '}
                <strong>{summary.habit.tasks_acknowledged_last_7_days}</strong> inbox item
                {summary.habit.tasks_acknowledged_last_7_days !== 1 ? 's' : ''} (visibility only).
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}

      <Card className="mb-6 border-gray-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Summary</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4 text-sm">
          <div>
            <span className="text-gray-500">Urgent</span>
            <p className="text-xl font-semibold text-midnight-blue">{summary?.urgent_count ?? 0}</p>
          </div>
          <div>
            <span className="text-gray-500">Upcoming</span>
            <p className="text-xl font-semibold text-midnight-blue">{summary?.upcoming_count ?? 0}</p>
          </div>
          <div>
            <span className="text-gray-500">In progress</span>
            <p className="text-xl font-semibold text-midnight-blue">{summary?.in_progress_count ?? 0}</p>
          </div>
          <div title="Tasks you snoozed; they return after the snooze date">
            <span className="text-gray-500">Snoozed</span>
            <p className="text-xl font-semibold text-midnight-blue">{summary?.snoozed_count ?? 0}</p>
          </div>
          {spendDisplay && (
            <div className="min-w-[10rem]" title={spendDisplay.hint}>
              <span className="text-gray-500">This month&apos;s spend (paid invoices)</span>
              <p className="text-xl font-semibold text-midnight-blue">{spendDisplay.amount}</p>
              <p className="text-xs text-gray-500 mt-0.5">{spend.invoice_count ?? 0} paid invoice(s) this month · UTC month</p>
            </div>
          )}
          <div className="w-full text-xs text-gray-500 space-y-1 mt-2 border-t border-gray-100 pt-3">
            {freshness?.score_updated_at && (
              <p>Compliance score updated: {formatWhen(freshness.score_updated_at)}</p>
            )}
            {freshness?.risk_signals_updated_at && (
              <p>Risk signals updated: {formatWhen(freshness.risk_signals_updated_at)}</p>
            )}
            {freshness?.last_automation_score_recalc_at && (
              <p>Last automated score recalc: {formatWhen(freshness.last_automation_score_recalc_at)}</p>
            )}
            {freshness?.last_automation_risk_refresh_at && (
              <p>Last automated risk refresh: {formatWhen(freshness.last_automation_risk_refresh_at)}</p>
            )}
            {freshness?.tasks_refreshed_at && <p>Tasks refreshed: {formatWhen(freshness.tasks_refreshed_at)}</p>}
          </div>
        </CardContent>
      </Card>

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
                  {p.nickname || p.name || p.address_line_1 || p.property_id}
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

      {loading && (
        <div className="flex justify-center py-16">
          <Loader2 className="w-10 h-10 animate-spin text-electric-teal" />
        </div>
      )}

      <Dialog open={Boolean(dismissModalTask)} onOpenChange={(open) => !open && setDismissModalTask(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Dismiss task from your inbox</DialogTitle>
            <DialogDescription className="text-left text-gray-600">
              This hides the card from your open lists. It does <strong>not</strong> satisfy a requirement, close a work order, or
              change compliance scores. Your reason is stored for audit and support.
            </DialogDescription>
          </DialogHeader>
          <textarea
            className="w-full min-h-[100px] border border-gray-200 rounded-lg p-3 text-sm"
            placeholder="Reason (required, min. 3 characters)"
            value={dismissReason}
            onChange={(e) => setDismissReason(e.target.value)}
            aria-label="Dismiss reason"
          />
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setDismissModalTask(null)}>
              Cancel
            </Button>
            <Button type="button" className="bg-midnight-blue hover:bg-midnight-blue/90" onClick={confirmDismissTask}>
              Dismiss task
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {!loading && !error && (
        <>
          <SectionBlock
            title="Urgent"
            tasks={urgent}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onOpenDismissModal={openDismissModal}
            onPrimaryNavigate={onPrimaryNavigate}
            onRunBusinessAction={runBusinessAction}
            onVisibilityTap={runVisibilityTap}
            onTaskTitleClick={onTaskTitleClick}
            overrideBusy={overrideBusyId}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage
            emptyHint="Nothing in the urgent queue. Good standing, or try another filter."
          />
          <SectionBlock
            title="Upcoming"
            tasks={upcoming}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onOpenDismissModal={openDismissModal}
            onPrimaryNavigate={onPrimaryNavigate}
            onRunBusinessAction={runBusinessAction}
            onVisibilityTap={runVisibilityTap}
            onTaskTitleClick={onTaskTitleClick}
            overrideBusy={overrideBusyId}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage
            emptyHint="No upcoming items in this view."
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
            onTaskTitleClick={onTaskTitleClick}
            overrideBusy={overrideBusyId}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage
            emptyHint="No in-progress items here — pending approvals and open issues appear in this section."
          />
          {snoozed.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Snoozed</h2>
              <p className="text-sm text-gray-500 mb-3">
                These stay out of your open lists until the date shown. Restore anytime to bring them back.
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
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Hidden (dismissed, reviewed, or legacy Done)</h2>
              <p className="text-sm text-gray-500 mb-3">
                You removed these from open lists only. Underlying obligations, scores, and jobs are unchanged unless you completed
                them elsewhere — restore anytime.
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
            onTaskTitleClick={onTaskTitleClick}
            overrideBusy={overrideBusyId}
            complianceBookingBusyId={complianceBookingBusyId}
            showComplianceBooking={showComplianceBooking}
            enableTriage={false}
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
                        <span className="font-medium text-midnight-blue">{actionLabel(row.action)}</span>
                        <span className="text-gray-500 font-mono text-xs truncate max-w-[12rem]" title={row.task_id}>
                          {row.task_id}
                        </span>
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
