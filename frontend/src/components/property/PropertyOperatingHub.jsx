import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, Wrench, Zap } from 'lucide-react';
import { toast } from 'sonner';
import apiClient, { clientAPI } from '../../api/client';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { complianceRequirementStatusLabel, requirementLabel } from '../../domain/presentDomain';
import { getEvidenceStatus } from '../../utils/evidenceStatus';
import { humanRiskType, humanSeverity, humanAction } from '../../utils/riskPresentation';
import { buildSafeQueryPath, buildEntityRoute, resolveClientPortalPath, resolveDocumentsPath } from '../../utils/clientPortalNavigation';
import { resolveTaskCta } from '../../utils/ctaRegistry';
import { PORTAL_COPY } from '../../utils/clientPortalCopy';
import { cn } from '../../lib/utils';
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
  return (
    r?.title ||
    (r?.requirement_code || r?.requirement_type ? requirementLabel(r.requirement_code || r.requirement_type) : null) ||
    r?.description ||
    r?.name ||
    '—'
  );
}

function rowDays(r) {
  return r.days_to_expiry != null ? r.days_to_expiry : daysLeft(rowExpiry(r));
}

function evidenceDocStatusLabel(doc) {
  const s = (doc?.status || '').toUpperCase();
  if (s === 'VERIFIED') return 'Confirmed';
  if (s === 'REJECTED') return 'Rejected';
  if (s === 'EXPIRED') return 'Expired';
  const hasExtraction = doc?.extraction_id || (doc?.ai_extraction?.status === 'completed' && doc?.ai_extraction?.data);
  if (hasExtraction && s !== 'VERIFIED') return 'Pending Confirmation';
  if (s === 'UPLOADED') return 'Extracted';
  if (!doc?.requirement_id) return 'Unlinked';
  return 'Uploaded';
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
  hubLatestDocuments,
  operatingFeedItems,
  operatingFeedLoading,
  setComplianceStatusFilter,
  openBookInspectionFromRisk,
  onOpenNotApplicable,
  setWoDetailDrawer,
  onAddWorkOrder,
  onCreateWoFromRiskDescription,
}) {
  const navigate = useNavigate();
  const {
    compliance: TAB_COMPLIANCE,
    maintenance: TAB_MAINTENANCE,
    evidence: TAB_EVIDENCE,
    timeline: TAB_TIMELINE,
    riskSignals: TAB_RISK_SIGNALS,
    contractors: TAB_CONTRACTORS,
  } = tabs;

  const handleEvidenceDocumentDownload = (doc) => {
    if (!doc?.document_id) return;
    apiClient
      .get(`/documents/${doc.document_id}/file`, { params: { download: true }, responseType: 'blob' })
      .then((res) => {
        const url = window.URL.createObjectURL(res.data);
        const a = document.createElement('a');
        a.href = url;
        a.download = doc.file_name || doc.original_filename || 'document';
        a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => toast.error('Could not download document'));
  };

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
                  return (
                    <li key={action.task_id || action.id} className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-midnight-blue">{action.title}</p>
                        {action.description ? <p className="text-xs text-gray-600 mt-1 line-clamp-3">{action.description}</p> : null}
                      </div>
                      {cta.route ? (
                        <Link
                          to={resolveClientPortalPath(cta.route, propertyId ? `/properties/${propertyId}` : '/properties')}
                          className={cn(portalPrimaryButtonClass, 'inline-flex w-full sm:w-auto justify-center no-underline shrink-0')}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {action.primary_action_label || PORTAL_COPY.viewDetails}
                        </Link>
                      ) : (
                        <span className="text-xs text-gray-500">No route — open Compliance or Maintenance.</span>
                      )}
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
                If obligations are overdue or jobs are open, they are listed below. You can still upload evidence or add a work order from the header.
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
              const sigActions = Array.isArray(s.suggested_actions) ? s.suggested_actions : ['create_issue', 'create_work_order'];
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
                    {sigActions.includes('create_work_order') && (
                      <Button
                        type="button"
                        className={cn(portalPrimaryButtonClass, 'w-full justify-center bg-electric-teal hover:bg-electric-teal/90')}
                        onClick={async () => {
                          if (hasFeature('maintenance_workflows')) {
                            try {
                              await clientAPI.createWorkOrderFromRiskSignal(s.signal_id, {});
                              toast.success('Work order created');
                              loadRiskSignals();
                              loadWorkOrders();
                            } catch (e) {
                              toast.error(e?.response?.data?.detail || 'Failed');
                            }
                          } else {
                            onCreateWoFromRiskDescription(s.recommended_action);
                          }
                        }}
                      >
                        <Wrench className="w-4 h-4 mr-2 shrink-0" />
                        {PORTAL_COPY.addWorkOrder}
                      </Button>
                    )}
                    {sigActions.includes('schedule_inspection') && hasFeature('compliance_engine') && hasFeature('maintenance_workflows') && (
                      <Button
                        type="button"
                        variant="outline"
                        className={cn(portalSecondaryButtonClass, 'w-full justify-center')}
                        onClick={() => openBookInspectionFromRisk(s.signal_id)}
                      >
                        Book compliance inspection
                      </Button>
                    )}
                    {sigActions.includes('schedule_inspection') && hasFeature('maintenance_workflows') && !hasFeature('compliance_engine') && (
                      <Button
                        type="button"
                        variant="outline"
                        className={cn(portalSecondaryButtonClass, 'w-full justify-center')}
                        onClick={async () => {
                          try {
                            await clientAPI.logInspectionIssueFromRiskSignal(s.signal_id, {});
                            toast.success('Inspection issue logged');
                            loadRiskSignals();
                          } catch (e) {
                            toast.error(e?.response?.data?.detail || 'Failed');
                          }
                        }}
                      >
                        Log inspection issue
                      </Button>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant="ghost" size="sm" className="min-h-10 text-gray-600" onClick={() => onSelectTab(TAB_RISK_SIGNALS)}>
                        {PORTAL_COPY.viewDetails}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="min-h-10 text-gray-600"
                        onClick={async () => {
                          try {
                            await clientAPI.updateRiskSignalStatus(s.signal_id, 'acknowledged');
                            loadRiskSignals();
                          } catch (_) {}
                        }}
                      >
                        Acknowledge
                      </Button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
          {(riskSignalsData.signals || []).filter((s) => (s.status || 'active') === 'active').length > 2 && (
            <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-3 w-full sm:w-auto')} onClick={() => onSelectTab(TAB_RISK_SIGNALS)}>
              All {PORTAL_COPY.riskSignal.toLowerCase()}s
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
                { label: 'Missing evidence', count: sum.missingEvidence, filter: 'MISSING', tone: 'text-midnight-blue' },
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
              <p className="font-medium text-midnight-blue">No obligations in a critical state.</p>
              <p className="mt-2 text-xs text-gray-500">Open Compliance for the full obligations matrix and filters.</p>
              <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-4')} onClick={() => onSelectTab(TAB_COMPLIANCE)}>
                Full {PORTAL_COPY.requirements.toLowerCase()}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <ul className="space-y-3">
            {hubPrioritizedRequirements.map((r) => {
              const st = (r.status || '').toUpperCase();
              const statusUi = getEvidenceStatus(r.status);
              const Icon = statusUi.icon;
              const linked = !!r.evidence_doc_id;
              const due = rowExpiry(r);
              const est = r.date_source === 'SYSTEM_ESTIMATED';
              const primaryLabel =
                ['PENDING', 'MISSING'].includes(st)
                  ? PORTAL_COPY.uploadDocument
                  : linked && ['OVERDUE', 'EXPIRED', 'EXPIRING_SOON'].includes(st)
                    ? 'Replace evidence'
                    : linked
                      ? PORTAL_COPY.viewDocuments
                      : PORTAL_COPY.viewDetails;
              const reqHref = buildEntityRoute({ requirement_id: rowReqId(r), property_id: propertyId, mode: 'requirement' }, '');
              return (
                <li key={rowReqId(r) || r.requirement_code} className="rounded-xl border border-gray-200 bg-white p-4 min-w-0 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-midnight-blue leading-snug">{rowTitle(r)}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs ${statusUi.className}`}>
                          <Icon className="w-3.5 h-3.5 shrink-0" />
                          {complianceRequirementStatusLabel(r.status)}
                        </span>
                        <span className="text-xs text-gray-500">Evidence: {linked ? 'Linked' : 'None'}</span>
                      </div>
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
                  <div className="flex flex-col gap-2 mt-4 sm:flex-row sm:flex-wrap">
                    <Button
                      type="button"
                      className={cn(portalPrimaryButtonClass, 'w-full sm:w-auto justify-center')}
                      onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: rowReqId(r) }))}
                    >
                      {primaryLabel}
                    </Button>
                    {reqHref ? (
                      <Link to={reqHref} className={cn(portalSecondaryButtonClass, 'inline-flex w-full sm:w-auto justify-center no-underline items-center')}>
                        {PORTAL_COPY.viewDetails}
                      </Link>
                    ) : null}
                    {['PENDING', 'MISSING'].includes(st) && (r.requirement_code || r.requirement_type) ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="min-h-10 text-gray-600 w-full sm:w-auto justify-center"
                        onClick={() =>
                          onOpenNotApplicable({
                            requirement_code: r.requirement_code || r.requirement_type,
                            title: rowTitle(r),
                          })
                        }
                      >
                        Not applicable
                      </Button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-4 w-full sm:w-auto')} onClick={() => onSelectTab(TAB_COMPLIANCE)}>
          Full obligations matrix
        </Button>
      </section>

      {hasFeature('maintenance_workflows') && (
        <section className="min-w-0" aria-labelledby="property-jobs-hub-heading">
          <h2 id="property-jobs-hub-heading" className="text-lg font-semibold text-midnight-blue border-b border-gray-200 pb-2 mb-3">
            Active {PORTAL_COPY.workOrders.toLowerCase()}
          </h2>
          {workOrdersLoading && hubActiveWorkOrders.length === 0 ? (
            <PortalLoadingPanel message="Loading jobs…" />
          ) : hubActiveWorkOrders.length === 0 ? (
            <Card className="border border-gray-200">
              <CardContent className="py-8 text-center text-sm text-gray-600">
                <p className="font-medium text-midnight-blue">No open maintenance jobs.</p>
                <p className="mt-2 text-xs text-gray-500">Create a work order from the header or open Maintenance for issues and history.</p>
                <Button
                  type="button"
                  className={cn(portalPrimaryButtonClass, 'mt-4 w-full sm:w-auto justify-center bg-electric-teal hover:bg-electric-teal/90')}
                  onClick={onAddWorkOrder}
                >
                  {PORTAL_COPY.addWorkOrder}
                </Button>
              </CardContent>
            </Card>
          ) : (
            <ul className="space-y-3">
              {hubActiveWorkOrders.slice(0, 6).map((wo) => (
                <li key={wo.work_order_id} className="rounded-xl border border-gray-200 p-4 min-w-0">
                  <p className="font-medium text-midnight-blue text-sm leading-snug">{wo.description || 'Work order'}</p>
                  <p className="text-xs text-gray-600 mt-2">
                    <span className="font-medium">{wo.status || '—'}</span>
                    {wo.sla_complete_by ? <span> · SLA {formatDate(wo.sla_complete_by)}</span> : null}
                    {wo.contractor_id || wo.contractor_name ? <span> · Contractor assigned</span> : wo.status === 'SCHEDULED' ? <span> · Scheduled</span> : null}
                  </p>
                  <div className="flex flex-col gap-2 mt-3 sm:flex-row">
                    <Button type="button" className={cn(portalPrimaryButtonClass, 'w-full sm:w-auto justify-center')} onClick={() => setWoDetailDrawer(wo.work_order_id)}>
                      {PORTAL_COPY.viewDetails}
                    </Button>
                    <Link
                      to={buildSafeQueryPath('/operations/work-orders', { work_order_id: wo.work_order_id })}
                      className={cn(portalSecondaryButtonClass, 'inline-flex w-full sm:w-auto justify-center no-underline items-center')}
                    >
                      Open in Operations
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <Button type="button" variant="ghost" className="mt-3 text-electric-teal min-h-10" onClick={() => onSelectTab(TAB_MAINTENANCE)}>
            Maintenance workspace
          </Button>
        </section>
      )}

      <section className="min-w-0" aria-labelledby="property-evidence-hub-heading">
        <h2 id="property-evidence-hub-heading" className="text-lg font-semibold text-midnight-blue border-b border-gray-200 pb-2 mb-3">
          Evidence and documents
        </h2>
        {evidenceLoading && !evidenceData ? (
          <PortalLoadingPanel message="Loading evidence…" />
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
                    <p className="text-xs text-gray-500">Total docs</p>
                    <p className="text-lg font-semibold text-midnight-blue">{evidenceData.summary.totalDocuments ?? 0}</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-600">Evidence summary will appear when loaded.</p>
              )}
              {hubLatestDocuments.length === 0 ? (
                <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50/50 px-4 py-6 text-center text-sm text-gray-600">
                  <p>No documents yet for this property.</p>
                  <Button
                    type="button"
                    className={cn(portalPrimaryButtonClass, 'mt-3 w-full sm:w-auto justify-center')}
                    onClick={() => navigate(resolveDocumentsPath(propertyId))}
                  >
                    {PORTAL_COPY.uploadDocument}
                  </Button>
                </div>
              ) : (
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Latest uploads</p>
                  <ul className="space-y-2">
                    {hubLatestDocuments.map((doc) => (
                      <li key={doc.document_id} className="flex flex-col gap-2 rounded-lg border border-gray-100 p-3 sm:flex-row sm:items-center sm:justify-between min-w-0">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-midnight-blue truncate">{doc.file_name || doc.original_filename || doc.document_id}</p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {evidenceDocStatusLabel(doc)} · {doc.uploaded_at ? formatRelativeTime(doc.uploaded_at) : '—'}
                          </p>
                        </div>
                        <div className="flex flex-col gap-2 sm:flex-row sm:shrink-0">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="min-h-11 w-full sm:w-auto"
                            onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}
                          >
                            {PORTAL_COPY.viewDocuments}
                          </Button>
                          <Button type="button" variant="ghost" size="sm" className="min-h-11 w-full sm:w-auto" onClick={() => handleEvidenceDocumentDownload(doc)}>
                            Download
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <Button type="button" className={cn(portalPrimaryButtonClass, 'w-full sm:w-auto justify-center')} onClick={() => navigate(resolveDocumentsPath(propertyId))}>
                  {PORTAL_COPY.uploadDocument}
                </Button>
                <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'w-full sm:w-auto justify-center')} onClick={() => onSelectTab(TAB_EVIDENCE)}>
                  Full evidence vault
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
              <p>No recent events in the last 30 days.</p>
              <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-4')} onClick={() => onSelectTab(TAB_TIMELINE)}>
                Open full timeline
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <ul className="space-y-2">
              {operatingFeedItems.map((item) => (
                <li key={item.id} className="rounded-lg border border-gray-100 bg-white px-3 py-3 text-sm min-w-0">
                  <p className="font-medium text-midnight-blue leading-snug">{item.title}</p>
                  {item.description ? <p className="text-xs text-gray-600 mt-1 line-clamp-2">{item.description}</p> : null}
                  <p className="text-xs text-gray-400 mt-2">{formatRelativeTime(item.timestamp)}</p>
                </li>
              ))}
            </ul>
            <Button type="button" variant="outline" className={cn(portalSecondaryButtonClass, 'mt-3 w-full sm:w-auto')} onClick={() => onSelectTab(TAB_TIMELINE)}>
              Full timeline
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
