import React, { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, Eye, RefreshCw, Upload, Wrench, Zap } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import { clientAPI } from '../../api/client';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { requirementTitleFromRow } from '../../domain/presentDomain';
import { humanRiskType, humanSeverity, humanAction } from '../../utils/riskPresentation';
import {
  buildEntityRoute,
  recordClientPortalInteraction,
  resolveClientPortalPath,
  resolveDocumentsPath,
} from '../../utils/clientPortalNavigation';
import { resolveTaskCta } from '../../utils/ctaRegistry';
import { useGuidedEvidenceModal } from '../../context/GuidedEvidenceModalContext';
import {
  executeRequirementPrimaryCta,
  GUIDED_CTA_UNAVAILABLE_TITLE,
} from '../../utils/requirementCtaParity';
import { buildRequirementShapedRowFromPriorityTask } from '../../utils/taskRequirementRowAdapter';
import { inboxTaskLinkedRequirementId } from '../../utils/portalRequirementAttention';
import { resolveRiskSignalPrimaryKey } from '../../utils/primaryActionResolver';
import { PORTAL_COPY } from '../../utils/clientPortalCopy';
import { cn } from '../../lib/utils';
import { humanizeOperatingFeedItems } from '../../utils/propertyOperatingActivityCopy';
import { isRequirementMissingDocument, requirementHasLinkedDocument } from '../../utils/propertyDocumentsMatrix';
import { isRedundantUploadStyleSecondaryAction } from '../../utils/complianceObligationPresent';
import {
  projectResolvedRequirementFromPriorityTask,
  projectResolvedRequirementSemantics,
} from '../../utils/resolvedRequirementViewModel';
import {
  getLifecycleTierBadge,
  getRequirementLifecycleCardShellClass,
} from '../../utils/requirementLifecyclePresentation';
import {
  PortalLoadingPanel,
  portalPrimaryButtonClass,
  portalSecondaryButtonClass,
} from '../client/ClientPortalPatterns';

function formatDate(d) {
  return d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
}

function formatRelativeTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = new Date();
  const sec = Math.floor((now - d) / 1000);
  if (sec < 60) return 'Just now';
  if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} hours ago`;
  if (sec < 172800) return 'Yesterday';
  if (sec < 604800) return `${Math.floor(sec / 86400)} days ago`;
  return formatDate(iso);
}

function daysLeft(d) {
  if (!d) return null;
  return Math.ceil((new Date(d) - new Date()) / (1000 * 60 * 60 * 24));
}

function rowExpiry(r) {
  return r.expiry_date || r.due_date;
}

function rowReqId(r) {
  return r.requirement_id || r.id;
}

function rowTitle(r) {
  return requirementTitleFromRow(r, 'compact');
}

function rowDays(r) {
  return r.days_to_expiry != null ? r.days_to_expiry : daysLeft(rowExpiry(r));
}

/**
 * Mobile-first operating surface for a single property (extracted from PropertyDetailPage).
 */
export default function PropertyOperatingHub({
  propertyId,
  hasFeature,
  tabs,
  onSelectTab,
  priorityActions,
  riskSignalsData,
  loadRiskSignals,
  loadWorkOrders,
  hubPrioritizedRequirements,
  getComplianceSummary,
  hubActiveWorkOrders,
  workOrdersLoading,
  evidenceData,
  evidenceLoading,
  operatingFeedItems,
  operatingFeedLoading,
  setComplianceStatusFilter,
  openBookInspectionFromRisk,
  onOpenNotApplicable,
  onCreateWoFromRiskDescription,
  onPlanRestrictedJobError,
  onRefreshAfterEvidence,
  /** Map from {@link requirementMapFromList} — merges full requirement rows into priority-task CTAs. */
  priorityTaskRequirementsById = null,
}) {
  const navigate = useNavigate();
  const { openGuidedEvidence } = useGuidedEvidenceModal();
  const {
    compliance: TAB_COMPLIANCE,
    maintenance: TAB_MAINTENANCE,
    evidence: TAB_EVIDENCE,
    timeline: TAB_TIMELINE,
    riskSignals: TAB_RISK_SIGNALS,
    contractors: TAB_CONTRACTORS,
  } = tabs;

  const operatingFeedDisplayItems = useMemo(
    () => humanizeOperatingFeedItems(operatingFeedItems).slice(0, 5),
    [operatingFeedItems]
  );

  const openJobKindBreakdown = useMemo(() => {
    let compliance = 0;
    let repair = 0;
    for (const wo of hubActiveWorkOrders || []) {
      if ((wo.work_order_kind || '').toUpperCase() === 'COMPLIANCE') compliance += 1;
      else repair += 1;
    }
    return { compliance, repair };
  }, [hubActiveWorkOrders]);

  return (
    <div className="space-y-8 min-w-0">
      <section className="min-w-0" aria-labelledby="property-urgent-heading">
        <h2 id="property-urgent-heading" className="text-lg font-semibold text-midnight-blue border-b border-gray-200 pb-2 mb-3">
          Urgent and next actions
        </h2>
        <p className="text-xs text-gray-500 mb-3">Sourced from your command center — same priorities as Today and the dashboard.</p>
        {priorityActions.actions?.length > 0 ? (
          <Card className="border border-electric-teal/40 bg-gradient-to-b from-electric-teal/[0.06] to-white shadow-sm" data-testid="property-priority-actions-panel">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2 text-midnight-blue">
                <Zap className="w-4 h-4 text-electric-teal shrink-0" />
                Do this next
              </CardTitle>
              <CardDescription>Each action opens the exact screen or entity to complete it.</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <ul className="divide-y divide-gray-100">
                {priorityActions.actions.map((action) => {
                  const cta = resolveTaskCta(action, 'primary');
                  const label =
                    (action.metadata?.take_action?.primary?.label
                      ? String(action.metadata.take_action.primary.label)
                      : null) ||
                    action.primary_action_label ||
                    PORTAL_COPY.viewDetails;
                  const semTaskReq = projectResolvedRequirementFromPriorityTask(
                    action,
                    priorityTaskRequirementsById,
                    propertyId,
                  );
                  const reqRow = buildRequirementShapedRowFromPriorityTask(action, priorityTaskRequirementsById);
                  const taReq = semTaskReq?.cta || null;

                  const legacyPrimary = (
                    <>
                      {cta.guidedEvidence ? (
                        <Button
                          type="button"
                          className={cn(portalPrimaryButtonClass, 'inline-flex w-full sm:w-auto justify-center shrink-0')}
                          data-testid="property-priority-action-legacy-guided"
                          onClick={(e) => {
                            e.stopPropagation();
                            openGuidedEvidence({
                              propertyId: cta.guidedEvidence.propertyId,
                              requirementId: cta.guidedEvidence.requirementId,
                              onSubmitted: onRefreshAfterEvidence,
                              initialEvidenceMode: cta.guidedEvidence.initialEvidenceMode || undefined,
                            });
                          }}
                        >
                          {label}
                        </Button>
                      ) : cta.route ? (
                        <Link
                          to={resolveClientPortalPath(cta.route, propertyId ? `/properties/${propertyId}` : '/properties')}
                          className={cn(portalPrimaryButtonClass, 'inline-flex w-full sm:w-auto justify-center no-underline shrink-0')}
                          data-testid="property-priority-action-legacy-link"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {label}
                        </Link>
                      ) : (
                        <span
                          className="text-xs text-gray-500"
                          data-testid="property-priority-action-legacy-none"
                        >
                          No route — open Compliance or Jobs & issues.
                        </span>
                      )}
                    </>
                  );

                  const primaryControl =
                    reqRow && taReq ? (
                      taReq.primary_action_handler === 'guided_evidence_error' ? (
                        <Button
                          type="button"
                          disabled
                          title={GUIDED_CTA_UNAVAILABLE_TITLE}
                          className={cn(
                            portalPrimaryButtonClass,
                            'inline-flex w-full sm:w-auto justify-center shrink-0 opacity-60 cursor-not-allowed',
                          )}
                          data-testid="property-priority-action-requirement-disabled"
                          data-requirement-cta-parity="1"
                        >
                          {label}
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          className={cn(portalPrimaryButtonClass, 'inline-flex w-full sm:w-auto justify-center shrink-0')}
                          data-testid="property-priority-action-requirement-primary"
                          data-requirement-cta-parity="1"
                          onClick={(e) => {
                            e.stopPropagation();
                            recordClientPortalInteraction('operating_hub_do_this_next_requirement_primary', {
                              property_id: propertyId,
                              requirement_id: inboxTaskLinkedRequirementId(action),
                              task_id: action.id || action.task_id,
                            });
                            const { handled } = executeRequirementPrimaryCta({
                              requirement: reqRow || {},
                              pagePropertyId: propertyId,
                              navigate: (to) =>
                                navigate(
                                  resolveClientPortalPath(typeof to === 'string' ? to : to.pathname, '/properties'),
                                ),
                              openGuidedEvidence,
                              onSubmitted: onRefreshAfterEvidence,
                              guidedInitialOverride: taReq.guided_initial_evidence_mode || undefined,
                            });
                            if (!handled) {
                              if (cta.guidedEvidence) {
                                openGuidedEvidence({
                                  propertyId: cta.guidedEvidence.propertyId,
                                  requirementId: cta.guidedEvidence.requirementId,
                                  onSubmitted: onRefreshAfterEvidence,
                                  initialEvidenceMode: cta.guidedEvidence.initialEvidenceMode || undefined,
                                });
                              } else if (cta.route) {
                                navigate(
                                  resolveClientPortalPath(
                                    cta.route,
                                    propertyId ? `/properties/${propertyId}` : '/properties',
                                  ),
                                );
                              }
                            }
                          }}
                        >
                          {label}
                        </Button>
                      )
                    ) : (
                      legacyPrimary
                    );

                  return (
                    <li
                      key={action.task_id || action.id}
                      className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-midnight-blue">{action.title}</p>
                        {action.description ? (
                          <p className="text-xs text-gray-600 mt-1 line-clamp-3">{action.description}</p>
                        ) : null}
                      </div>
                      {primaryControl}
                    </li>
                  );
                })}
              </ul>
            </CardContent>
          </Card>
        ) : (
          <Card className="border border-gray-200 bg-gray-50/60">
            <CardContent className="py-6 text-sm text-gray-600">
              <p className="font-medium text-midnight-blue">Nothing urgent from the command center for this property.</p>
              <p className="mt-2 text-xs text-gray-500">
                If requirements are overdue or jobs are open, they are listed below. You can still add documents or start work from the property header.
              </p>
            </CardContent>
          </Card>
        )}
      </section>

      {hasFeature('predictive_maintenance') && (riskSignalsData?.signals || []).filter((s) => (s.status || 'active') === 'active').length > 0 && (
        <section className="min-w-0" aria-labelledby="property-risk-hub-heading">
          <h2 id="property-risk-hub-heading" className="text-lg font-semibold text-midnight-blue border-b border-gray-200 pb-2 mb-3 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
            {PORTAL_COPY.riskSignalsActiveHeading}
          </h2>
          <ul className="space-y-3">
            {(riskSignalsData.signals || []).filter((s) => (s.status || 'active') === 'active').slice(0, 2).map((s) => {
              const hasMaint = hasFeature('maintenance_workflows');
              const hasComp = hasFeature('compliance_engine');
              const { key: primaryKey, label: primaryLabel } = resolveRiskSignalPrimaryKey(s, hasMaint, hasComp);
              const onCreateWo = async () => {
                if (hasMaint) {
                  try {
                    await clientAPI.createWorkOrderFromRiskSignal(s.signal_id, {});
                    toast.success('Job started');
                    loadRiskSignals();
                    loadWorkOrders();
                  } catch (e) {
                    if (onPlanRestrictedJobError?.(e, { propertyId })) return;
                    toast.error(e?.response?.data?.detail || 'Failed');
                  }
                } else {
                  onCreateWoFromRiskDescription(s.recommended_action);
                }
              };
              const runPrimary = async () => {
                if (primaryKey === 'compliance_inspection') {
                  openBookInspectionFromRisk(s.signal_id);
                  return;
                }
                if (primaryKey === 'log_inspection_issue') {
                  try {
                    await clientAPI.logInspectionIssueFromRiskSignal(s.signal_id, {});
                    toast.success('Logged for follow-up');
                    loadRiskSignals();
                  } catch (e) {
                    toast.error(e?.response?.data?.detail || 'Failed');
                  }
                  return;
                }
                if (primaryKey === 'maintenance_job') {
                  await onCreateWo();
                  return;
                }
                if (primaryKey === 'maintenance_issue') {
                  try {
                    await clientAPI.createIssueFromRiskSignal(s.signal_id, {});
                    toast.success('Logged for follow-up');
                    loadRiskSignals();
                  } catch (e) {
                    toast.error(e?.response?.data?.detail || 'Failed');
                  }
                  return;
                }
                onSelectTab(TAB_RISK_SIGNALS);
              };
              return (
                <li key={s.signal_id} className="rounded-xl border border-amber-200/80 bg-amber-50/40 p-4 min-w-0">
                  <p className="font-medium text-midnight-blue">{humanRiskType(s)}</p>
                  <p className="text-sm text-gray-700 mt-1">{humanAction(s.recommended_action, s)}</p>
                  <span
                    className={`inline-block mt-2 text-xs px-2 py-0.5 rounded border ${
                      ['high', 'critical'].includes((s.risk_level || '').toLowerCase())
                        ? 'bg-amber-100 text-amber-900 border-amber-200'
                        : 'bg-white text-gray-700 border-gray-200'
                    }`}
                  >
                    {humanSeverity(s.risk_level)}
                  </span>
                  <div className="flex flex-col gap-2 mt-3">
                    <Button
                      type="button"
                      className={cn(
                        portalPrimaryButtonClass,
                        'w-full justify-center bg-electric-teal hover:bg-electric-teal/90',
                        primaryKey === 'maintenance_job' ? 'inline-flex items-center justify-center' : '',
                      )}
                      onClick={runPrimary}
                    >
                      {primaryKey === 'maintenance_job' ? <Wrench className="w-4 h-4 mr-2 shrink-0" /> : null}
                      {primaryLabel}
                    </Button>
                    <Button type="button" variant="ghost" size="sm" className="min-h-10 text-gray-600 w-full justify-center" onClick={() => onSelectTab(TAB_RISK_SIGNALS)}>
                      {PORTAL_COPY.viewDetails}
                    </Button>
                    <button
                      type="button"
                      className="text-xs text-gray-500 hover:text-midnight-blue text-left underline"
                      onClick={async () => {
                        try {
                          await clientAPI.updateRiskSignalStatus(s.signal_id, 'acknowledged');
                          loadRiskSignals();
                        } catch (_) {}
                      }}
                    >
                      Acknowledge
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
          {(riskSignalsData.signals || []).filter((s) => (s.status || 'active') === 'active').length > 2 && (
            <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-3 w-full sm:w-auto')} onClick={() => onSelectTab(TAB_RISK_SIGNALS)}>
              View all risk signals
            </Button>
          )}
        </section>
      )}

      <section className="min-w-0" aria-labelledby="property-req-hub-heading">
        <h2 id="property-req-hub-heading" className="text-lg font-semibold text-midnight-blue border-b border-gray-200 pb-2 mb-3">
          {PORTAL_COPY.requirements} needing attention
        </h2>
        {(() => {
          const sum = getComplianceSummary();
          return (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4 text-center">
              {[
                { label: 'Overdue', count: sum.overdue, filter: 'OVERDUE', tone: 'text-red-600' },
                { label: 'Expiring', count: sum.expiringSoon, filter: 'EXPIRING_SOON', tone: 'text-amber-600' },
                { label: 'Missing documents', count: sum.missingDocuments, filter: 'MISSING', tone: 'text-midnight-blue' },
                { label: 'Valid', count: sum.valid, filter: 'VALID', tone: 'text-green-700' },
              ].map((p) => (
                <button
                  key={p.filter}
                  type="button"
                  onClick={() => {
                    setComplianceStatusFilter(p.filter === 'VALID' ? 'VALID' : p.filter);
                    onSelectTab(TAB_COMPLIANCE);
                  }}
                  className="rounded-lg border border-gray-200 bg-white px-2 py-3 text-left hover:bg-gray-50 min-h-[4.5rem]"
                >
                  <p className="text-xs text-gray-500 uppercase tracking-wide">{p.label}</p>
                  <p className={`text-xl font-bold ${p.tone}`}>{p.count}</p>
                </button>
              ))}
            </div>
          );
        })()}
        {hubPrioritizedRequirements.length === 0 ? (
          <Card className="border border-gray-200">
            <CardContent className="py-8 text-center text-sm text-gray-600">
              <p className="font-medium text-midnight-blue">No requirements in a critical state.</p>
              <p className="mt-2 text-xs text-gray-500">Open Compliance for the full requirements matrix and filters.</p>
              <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-4')} onClick={() => onSelectTab(TAB_COMPLIANCE)}>
                Full {PORTAL_COPY.requirements.toLowerCase()}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <ul className="space-y-3">
            {hubPrioritizedRequirements.map((r) => {
              const sem = projectResolvedRequirementSemantics(r, { pagePropertyId: propertyId });
              const statusUi = sem.evidenceStatusForStatus(r.status);
              const Icon = statusUi.icon;
              const tierBadge = getLifecycleTierBadge(r);
              const linked = requirementHasLinkedDocument(r);
              const due = rowExpiry(r);
              const est = r.date_source === 'SYSTEM_ESTIMATED';
              const needsDocument = isRequirementMissingDocument(r);
              const rid = rowReqId(r);
              const ta = sem.cta;
              const showHubSecondary = ta.secondary_action?.route && !isRedundantUploadStyleSecondaryAction(ta);
              const docsHref = resolveDocumentsPath(propertyId, rid ? { requirement_id: rid } : {});
              const reqHref = buildEntityRoute({ requirement_id: rid, property_id: propertyId, mode: 'requirement' }, '');
              const primaryClick = () => {
                if (ta.primary_action_handler === 'guided_evidence_error') return;
                const { handled } = executeRequirementPrimaryCta({
                  requirement: r,
                  pagePropertyId: propertyId,
                  navigate: (to) =>
                    navigate(resolveClientPortalPath(typeof to === 'string' ? to : to.pathname, '/properties')),
                  openGuidedEvidence,
                  onSubmitted: onRefreshAfterEvidence,
                  guidedInitialOverride: ta.guided_initial_evidence_mode || undefined,
                });
                if (!handled) {
                  const route = ta.primary_route || docsHref;
                  if (route) navigate(resolveClientPortalPath(route, '/properties'));
                }
              };
              return (
                <li
                  key={rowReqId(r) || r.requirement_code}
                  className={cn(getRequirementLifecycleCardShellClass(r), 'p-4 min-w-0')}
                  data-testid={tierBadge ? `hub-req-tier-${rid || 'unknown'}` : undefined}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-midnight-blue leading-snug">{rowTitle(r)}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs ${statusUi.className}`}>
                          <Icon className="w-3.5 h-3.5 shrink-0" />
                          {statusUi.text}
                        </span>
                        {tierBadge ? (
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${tierBadge.className}`}>
                            {tierBadge.text}
                          </span>
                        ) : null}
                        <span className="text-xs text-gray-500">Document: {linked ? 'Linked' : 'None'}</span>
                      </div>
                      {statusUi.subline ? (
                        <p className="text-xs text-gray-500 mt-1 max-w-prose">{statusUi.subline}</p>
                      ) : null}
                      {due ? (
                        <p className="text-xs text-gray-600 mt-2">
                          {est ? `${PORTAL_COPY.estimatedDate}: ` : 'Due: '}
                          <span className="font-medium">{formatDate(due)}</span>
                          {rowDays(r) != null ? (
                            <span className="text-gray-500">
                              {' '}
                              ({rowDays(r) < 0 ? `${Math.abs(rowDays(r))}d overdue` : `${rowDays(r)}d left`})
                            </span>
                          ) : null}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <div className="mt-4 flex w-full max-w-lg flex-col gap-2">
                    <Button
                      type="button"
                      className={cn(portalPrimaryButtonClass, 'w-full justify-center')}
                      disabled={ta.primary_action_handler === 'guided_evidence_error'}
                      title={ta.primary_action_handler === 'guided_evidence_error' ? GUIDED_CTA_UNAVAILABLE_TITLE : undefined}
                      onClick={primaryClick}
                    >
                      {ta.primary_intent === 'upload_evidence' && ta.primary_action_handler === 'navigate' ? (
                        <Upload className="w-3.5 h-3.5 mr-1 shrink-0 inline" aria-hidden />
                      ) : null}
                      {ta.actionType === 'JOB' ? <RefreshCw className="w-3.5 h-3.5 mr-1 shrink-0 inline" aria-hidden /> : null}
                      {ta.actionType === 'OBLIGATION' ? <Eye className="w-3.5 h-3.5 mr-1 shrink-0 inline" aria-hidden /> : null}
                      {ta.primary_action_label}
                    </Button>
                    {showHubSecondary ? (
                      <Button
                        type="button"
                        variant="outline"
                        className="min-h-10 w-full justify-center border-gray-300 text-gray-800 text-sm font-normal"
                        onClick={() =>
                          ta.secondary_action.external
                            ? window.open(ta.secondary_action.route, '_blank', 'noopener,noreferrer')
                            : navigate(ta.secondary_action.route)
                        }
                      >
                        {ta.secondary_action.label}
                      </Button>
                    ) : null}
                    {reqHref ? (
                      <Link
                        to={reqHref}
                        className="text-left text-xs font-normal text-gray-600 hover:text-midnight-blue py-0.5 underline-offset-2 decoration-gray-300 hover:underline hover:decoration-midnight-blue/40 no-underline"
                      >
                        View details
                      </Link>
                    ) : null}
                    {needsDocument && (r.requirement_code || r.requirement_type) ? (
                      <button
                        type="button"
                        className="text-left text-xs font-normal text-gray-500 hover:text-gray-700 py-0.5"
                        onClick={() =>
                          onOpenNotApplicable({
                            requirement_code: r.requirement_code || r.requirement_type,
                            title: rowTitle(r),
                          })
                        }
                      >
                        Not applicable
                      </button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-4 w-full sm:w-auto')} onClick={() => onSelectTab(TAB_COMPLIANCE)}>
          Full requirements matrix
        </Button>
      </section>

      {hasFeature('maintenance_workflows') && (
        <section className="min-w-0" aria-labelledby="property-jobs-hub-heading">
          <h2 id="property-jobs-hub-heading" className="text-lg font-semibold text-midnight-blue border-b border-gray-200 pb-2 mb-3">
            Jobs
          </h2>
          {workOrdersLoading && hubActiveWorkOrders.length === 0 ? (
            <PortalLoadingPanel message="Loading jobs…" />
          ) : (
            <Card className="border border-gray-200">
              <CardContent className="py-5 text-sm text-gray-700 space-y-3">
                {hubActiveWorkOrders.length === 0 ? (
                  <>
                    <p className="font-medium text-midnight-blue">No open jobs.</p>
                    <p className="text-xs text-gray-500">Create a job from the header when you need one. Full list and history live under Jobs & issues.</p>
                  </>
                ) : (
                  <>
                    <p className="text-midnight-blue">
                      <span className="font-semibold">{hubActiveWorkOrders.length}</span> open{' '}
                      {hubActiveWorkOrders.length === 1 ? 'job' : 'jobs'} for this property.
                    </p>
                    {(openJobKindBreakdown.compliance > 0 || openJobKindBreakdown.repair > 0) && (
                      <p className="text-xs text-gray-600">
                        {openJobKindBreakdown.compliance > 0 && (
                          <span>
                            {openJobKindBreakdown.compliance} compliance job{openJobKindBreakdown.compliance === 1 ? '' : 's'}
                          </span>
                        )}
                        {openJobKindBreakdown.compliance > 0 && openJobKindBreakdown.repair > 0 && <span> · </span>}
                        {openJobKindBreakdown.repair > 0 && (
                          <span>
                            {openJobKindBreakdown.repair} repair / maintenance job{openJobKindBreakdown.repair === 1 ? '' : 's'}
                          </span>
                        )}
                      </p>
                    )}
                    <p className="text-xs text-gray-500">Open Jobs & issues to review status, assign contractors, and close work.</p>
                  </>
                )}
                <Button type="button" className={cn(portalPrimaryButtonClass, 'w-full sm:w-auto justify-center')} onClick={() => onSelectTab(TAB_MAINTENANCE)}>
                  Jobs & issues
                </Button>
              </CardContent>
            </Card>
          )}
        </section>
      )}

      <section className="min-w-0" aria-labelledby="property-documents-hub-heading">
        <h2 id="property-documents-hub-heading" className="text-lg font-semibold text-midnight-blue border-b border-gray-200 pb-2 mb-3">
          Documents
        </h2>
        {evidenceLoading && !evidenceData ? (
          <PortalLoadingPanel message="Loading documents…" />
        ) : (
          <Card className="border border-gray-200">
            <CardContent className="pt-4 space-y-4">
              {evidenceData?.summary ? (
                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <div className="rounded-lg bg-gray-50 px-3 py-2 border border-gray-100">
                    <p className="text-xs text-gray-500">Missing (critical)</p>
                    <p className="text-lg font-semibold text-midnight-blue">{evidenceData.summary.missingCriticalEvidence ?? 0}</p>
                  </div>
                  <div className="rounded-lg bg-gray-50 px-3 py-2 border border-gray-100">
                    <p className="text-xs text-gray-500">{PORTAL_COPY.awaitingVerification}</p>
                    <p className="text-lg font-semibold text-amber-700">{evidenceData.summary.pendingConfirmation ?? 0}</p>
                  </div>
                  <div className="rounded-lg bg-gray-50 px-3 py-2 border border-gray-100">
                    <p className="text-xs text-gray-500">Linked</p>
                    <p className="text-lg font-semibold text-green-700">{evidenceData.summary.linked ?? 0}</p>
                  </div>
                  <div className="rounded-lg bg-gray-50 px-3 py-2 border border-gray-100">
                    <p className="text-xs text-gray-500">Total documents</p>
                    <p className="text-lg font-semibold text-midnight-blue">{evidenceData.summary.totalDocuments ?? 0}</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-600">Document summary will appear when loaded.</p>
              )}
              <p className="text-xs text-gray-500">
                Files you have provided for this property. Open the Documents tab for uploads and links to requirements.
              </p>
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <Button type="button" className={cn(portalPrimaryButtonClass, 'w-full sm:w-auto justify-center')} onClick={() => onSelectTab(TAB_EVIDENCE)}>
                  View all documents
                </Button>
                <Button type="button" variant="ghost" className="min-h-10 text-electric-teal w-full sm:w-auto justify-center" onClick={() => navigate(resolveDocumentsPath(propertyId))}>
                  {PORTAL_COPY.uploadDocument}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </section>

      <section className="min-w-0" aria-labelledby="property-feed-heading">
        <h2 id="property-feed-heading" className="text-lg font-semibold text-midnight-blue border-b border-gray-200 pb-2 mb-3">
          Recent activity
        </h2>
        {operatingFeedLoading ? (
          <PortalLoadingPanel message="Loading activity…" />
        ) : operatingFeedItems.length === 0 ? (
          <Card className="border border-gray-200">
            <CardContent className="py-8 text-center text-sm text-gray-600">
              <p>No recent highlights in the last 30 days.</p>
              <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-4')} onClick={() => onSelectTab(TAB_TIMELINE)}>
                View full history
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <p className="text-xs text-gray-500 mb-3">Recent highlights from the last 30 days — open the timeline for the full audit trail.</p>
            <ul className="space-y-2">
              {operatingFeedDisplayItems.map((item) => (
                <li key={item.id} className="rounded-lg border border-gray-100 bg-white px-3 py-3 text-sm min-w-0">
                  <p className="font-medium text-midnight-blue leading-snug">{item.title}</p>
                  {item.description ? <p className="text-xs text-gray-600 mt-1 line-clamp-2">{item.description}</p> : null}
                  <p className="text-xs text-gray-400 mt-2">{formatRelativeTime(item.timestamp)}</p>
                </li>
              ))}
            </ul>
            <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-3 w-full sm:w-auto')} onClick={() => onSelectTab(TAB_TIMELINE)}>
              View full history
            </Button>
          </>
        )}
      </section>

      {hasFeature('contractor_network') && (
        <section className="min-w-0 border-t border-gray-100 pt-6">
          <Button type="button" variant="ghost" className="min-h-10 text-gray-600 -ml-2" onClick={() => onSelectTab(TAB_CONTRACTORS)}>
            Contractors for this property →
          </Button>
        </section>
      )}
    </div>
  );
}
