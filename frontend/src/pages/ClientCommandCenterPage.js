/**
 * Client Command Center — single screen: synthesized verdict, compliance, priority snapshot,
 * portfolio summary, and jobs ranked by operational importance (existing APIs only).
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { clientAPI, parseApiError } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import ErrorBanner from '../components/ErrorBanner';
import { AlertCircle, Gauge, Sparkles, Building2, Wrench, ChevronRight, CheckCircle2 } from 'lucide-react';
import { recordClientPortalInteraction, resolveClientPortalPath } from '../utils/clientPortalNavigation';
import { resolveTaskCta } from '../utils/ctaRegistry';
import {
  inboxTitleForDisplay,
  requirementLabel,
  urgencyLevelLabel,
  workOrderStatusLabel,
} from '../domain/presentDomain';
import { workOrderKindClientLabel } from '../utils/jobWorkflowUi';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import {
  aggregateJobSignals,
  attentionBadgeForJob,
  buildCommandCenterVerdict,
  countPropertiesAtRisk,
  hasTruthyIso,
  isActiveWorkOrder,
  isAwaitingProof,
  isCommandCenterAllClearEmpty,
  isCommandCenterCalmSnapshot,
  isOperationalHold,
  rankWorkOrdersByAttention,
} from '../utils/clientCommandCenter';

const KPI_NO_DATA = 'No data yet';

function formatDashboardGrade(grade) {
  if (grade == null || grade === '' || grade === '—') return KPI_NO_DATA;
  return grade;
}

function complianceStripClasses(color) {
  const c = String(color || '').toLowerCase();
  if (c === 'green') return 'border-green-200 bg-green-50 text-green-950';
  if (c === 'red') return 'border-red-200 bg-red-50 text-red-950';
  return 'border-amber-200 bg-amber-50 text-amber-950';
}

function verdictBannerClasses(tone) {
  if (tone === 'calm') return 'border-green-200 bg-green-50/90 text-green-950';
  if (tone === 'critical') return 'border-red-200 bg-red-50/90 text-red-950';
  return 'border-amber-200 bg-amber-50/90 text-amber-950';
}

export default function ClientCommandCenterPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { hasFeature } = useEntitlements();
  const isClientUser = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;
  const predictiveEnabled = hasFeature('predictive_maintenance');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [bundle, setBundle] = useState(null);
  const [portfolioSummary, setPortfolioSummary] = useState(null);
  const [workOrdersRaw, setWorkOrdersRaw] = useState(null);

  useEffect(() => {
    if (!isClientUser) {
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError('');

    const maintenanceEnabled = hasFeature('maintenance_workflows');
    const tasks = [
      clientAPI.getCommandCenter({}).then((r) => r.data),
      clientAPI.getComplianceSummary().then((r) => r.data),
    ];
    if (maintenanceEnabled) {
      tasks.push(clientAPI.getMaintenanceWorkOrders({ skip: 0, limit: 200 }).then((r) => r.data));
    }

    Promise.all(
      tasks.map((p) =>
        p.then((data) => ({ ok: true, data })).catch((err) => ({ ok: false, err }))
      )
    ).then((results) => {
      if (cancelled) return;
      const [ccRes, psRes, woRes] = maintenanceEnabled ? results : [...results, { ok: false, err: null }];
      const cc = ccRes.ok && ccRes.data && typeof ccRes.data === 'object' ? ccRes.data : null;
      const ps = psRes.ok && psRes.data && typeof psRes.data === 'object' ? psRes.data : null;
      const wo =
        maintenanceEnabled && woRes?.ok && woRes.data && typeof woRes.data === 'object' ? woRes.data : null;
      if (!ccRes.ok && ccRes.err?.response?.status !== 403) {
        setError(parseApiError(ccRes.err, 'Command center snapshot could not be loaded'));
      } else if (!cc && !ps && !wo) {
        setError('Command center data could not be loaded.');
      } else {
        setError('');
      }
      setBundle(cc);
      setPortfolioSummary(ps);
      setWorkOrdersRaw(maintenanceEnabled ? wo : null);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [isClientUser, hasFeature]);

  const urgentCount = bundle?.urgent_actions?.length ?? 0;
  const urgentTop = useMemo(() => (bundle?.urgent_actions || []).slice(0, 5), [bundle?.urgent_actions]);
  const riskCount = bundle?.upcoming_risks?.length ?? 0;
  const summary = bundle?.compliance_status_summary;

  const activeJobs = useMemo(() => {
    const list = workOrdersRaw?.work_orders;
    if (!Array.isArray(list)) return [];
    return list.filter(isActiveWorkOrder);
  }, [workOrdersRaw]);

  const rankedJobs = useMemo(() => rankWorkOrdersByAttention(activeJobs, 8), [activeJobs]);

  const jobSignals = useMemo(() => aggregateJobSignals(activeJobs), [activeJobs]);

  const breachedJobCount = useMemo(
    () => activeJobs.filter((wo) => hasTruthyIso(wo.sla_breached_at)).length,
    [activeJobs]
  );
  const blockedJobCount = useMemo(
    () => activeJobs.filter((wo) => isOperationalHold(wo)).length,
    [activeJobs]
  );
  const awaitingProofJobCount = useMemo(() => activeJobs.filter((wo) => isAwaitingProof(wo)).length, [activeJobs]);

  const propertiesAtRisk = useMemo(() => countPropertiesAtRisk(portfolioSummary), [portfolioSummary]);

  const propertyLabelById = useMemo(() => {
    const m = new Map();
    for (const p of portfolioSummary?.properties || []) {
      const id = p.property_id;
      if (!id) continue;
      const addr = [p.address_line_1, p.city, p.postcode].filter(Boolean).join(', ');
      const lbl = String(p.nickname || p.name || addr || '').trim();
      if (lbl) m.set(id, lbl);
    }
    return m;
  }, [portfolioSummary]);

  const verdict = useMemo(
    () =>
      buildCommandCenterVerdict({
        urgentCount,
        riskCount,
        predictiveEnabled,
        summary,
        propertiesAtRisk,
        breachedJobCount,
        blockedJobCount,
        awaitingProofCount: awaitingProofJobCount,
      }),
    [
      urgentCount,
      riskCount,
      predictiveEnabled,
      summary,
      propertiesAtRisk,
      breachedJobCount,
      blockedJobCount,
      awaitingProofJobCount,
    ]
  );

  const maintenanceEnabled = hasFeature('maintenance_workflows');

  const allClearEmpty = isCommandCenterAllClearEmpty({
    urgentCount,
    predictiveEnabled,
    riskCount,
    activeJobsLength: activeJobs.length,
    summary,
    propertiesAtRisk,
  });

  const calmSnapshot = isCommandCenterCalmSnapshot({
    urgentCount,
    predictiveEnabled,
    riskCount,
    breachedJobCount,
    blockedJobCount,
    summary,
    propertiesAtRisk,
  });

  const onUrgentClick = (t) => {
    const url = resolveTaskCta(t, 'primary').route || t.primary_action_url || t.cta_url;
    if (url && url.startsWith('/')) {
      const target = resolveClientPortalPath(url, '/today');
      recordClientPortalInteraction('command_center_urgent_task', { task_id: t.id, target });
      navigate(target);
    } else if (url) {
      window.location.assign(url);
    } else {
      navigate('/today');
    }
  };

  if (!isClientUser) {
    return (
      <div className={portalPageRoot} data-testid="command-center-forbidden">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {user && !user.client_id
              ? 'Client not found. Use the correct portal for your role.'
              : 'Sign in as a client to view the command center.'}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={portalPageRoot} data-testid="command-center-loading">
        <PortalLoadingPanel message="Loading command center…" />
      </div>
    );
  }

  return (
    <div className={portalPageRoot} data-testid="command-center-root">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-midnight-blue flex items-center gap-2">
            <Gauge className="h-7 w-7 text-teal-600 shrink-0" aria-hidden />
            Command center
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            One place for your verdict, compliance posture, and what to push on first—not your full task inbox.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to="/today">Open Today inbox</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/dashboard">Dashboard</Link>
          </Button>
        </div>
      </div>

      <ErrorBanner message={error} />

      {/* Verdict banner */}
      <div
        className={`mb-6 rounded-xl border px-4 py-4 sm:px-5 sm:py-5 ${verdictBannerClasses(verdict.tone)}`}
        data-testid="command-center-verdict"
        role="status"
      >
        <p className="text-lg font-semibold leading-snug">{verdict.line}</p>
        {verdict.subline ? <p className="text-sm mt-2 opacity-90">{verdict.subline}</p> : null}
      </div>

      {allClearEmpty && !error && (
        <Card
          className="mb-6 border-green-200 bg-green-50/50 shadow-sm"
          data-testid="command-center-all-clear"
        >
          <CardContent className="pt-6 pb-6 flex flex-col sm:flex-row gap-4 sm:items-center">
            <CheckCircle2 className="h-12 w-12 text-green-600 shrink-0" aria-hidden />
            <div>
              <p className="font-semibold text-green-950 text-lg">Nothing needs your immediate attention.</p>
              <p className="text-sm text-green-900/90 mt-1">
                No urgent actions, no major risks in this snapshot, and no active jobs. Check Today from time to time
                for new items.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 1. Status summary */}
      <Card className="mb-6 border border-gray-200 shadow-sm" data-testid="command-center-status">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Compliance &amp; risk posture</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {summary && summary.score != null ? (
            <div
              className={`rounded-xl border p-4 ${complianceStripClasses(summary.color)}`}
              data-testid="command-center-compliance-strip"
            >
              <p className="text-xs font-semibold uppercase tracking-wide opacity-90">Overall compliance</p>
              <p className="text-lg font-semibold mt-1">
                Grade {formatDashboardGrade(summary.grade)} · Score {Math.round(Number(summary.score))}
              </p>
              {summary.message ? <p className="text-sm mt-2 opacity-95">{summary.message}</p> : null}
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs opacity-90">
                {summary.requirements_overdue != null && <span>Overdue: {summary.requirements_overdue}</span>}
                {summary.requirements_expiring_soon != null && (
                  <span>Expiring soon: {summary.requirements_expiring_soon}</span>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-600">Compliance score is not available yet.</p>
          )}
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <span className="text-gray-700">
              <span className="font-medium text-midnight-blue">{riskCount}</span> open issue
              {riskCount === 1 ? '' : 's'}
              {!predictiveEnabled && <span className="text-gray-500"> (issue insights not enabled)</span>}
            </span>
            {predictiveEnabled && riskCount > 0 && (
              <Button variant="link" className="h-auto p-0 text-electric-teal" asChild>
                <Link to="/operations/risk-signals">Review issues</Link>
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 2. Priority snapshot (distinct from Today) */}
      <Card className="mb-6 border border-gray-200 shadow-sm" data-testid="command-center-urgent">
        <CardHeader className="pb-2 flex flex-row items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-teal-600" />
              What to push on first
            </CardTitle>
            <p className="text-xs text-gray-500 mt-1 font-normal">
              Top of your priority queue (same items as Today, shown here as a snapshot only).
            </p>
          </div>
          <Button variant="outline" size="sm" className="shrink-0" asChild>
            <Link to="/today">Full Today inbox</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {urgentTop.length > 0 ? (
            <ul className="space-y-3 text-sm">
              {urgentTop.map((t, idx) => (
                <li
                  key={t.id || t.task_id || t.title}
                  className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-3 border-b border-gray-100 pb-3 last:border-0 last:pb-0"
                >
                  <div className="flex gap-2 min-w-0">
                    <span className="text-xs font-semibold text-gray-400 w-5 shrink-0 pt-0.5">{idx + 1}.</span>
                    <div className="min-w-0">
                      <button
                        type="button"
                        className="text-left text-midnight-blue hover:underline font-medium break-words"
                        onClick={() => onUrgentClick(t)}
                      >
                        {inboxTitleForDisplay(t)}
                      </button>
                      {(t.urgency_level || t.priority_level) && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          Priority: {urgencyLevelLabel(t.urgency_level || t.priority_level)}
                        </p>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-gray-500 shrink-0 sm:text-right sm:max-w-[36%] break-words pl-7 sm:pl-0">
                    {[t.property_label, t.timing_label].filter(Boolean).join(' · ')}
                  </span>
                </li>
              ))}
            </ul>
          ) : calmSnapshot ? (
            <p className="text-sm text-gray-700">
              <span className="font-medium text-green-800">No urgent actions right now.</span> Your Today inbox may
              still have scheduled or lower-urgency items—open it when you want the full list.
            </p>
          ) : (
            <p className="text-sm text-gray-600">
              No urgent items in this snapshot. Use Today for snooze, dismiss, and the complete inbox.
            </p>
          )}
        </CardContent>
      </Card>

      {/* 3. Compliance overview (properties) */}
      <Card className="mb-6 border border-gray-200 shadow-sm" data-testid="command-center-properties">
        <CardHeader className="pb-2 flex flex-row items-center justify-between gap-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Building2 className="h-4 w-4 text-teal-600" />
            Portfolio snapshot
          </CardTitle>
          <Button variant="outline" size="sm" asChild>
            <Link to="/properties">Properties</Link>
          </Button>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {portfolioSummary ? (
            <>
              <div className="flex flex-wrap gap-x-6 gap-y-2">
                <span>
                  <span className="font-medium text-midnight-blue">{portfolioSummary.properties?.length ?? 0}</span>{' '}
                  propert
                  {(portfolioSummary.properties?.length ?? 0) === 1 ? 'y' : 'ies'}
                </span>
                {portfolioSummary.portfolio_score != null && (
                  <span>
                    Portfolio score:{' '}
                    <span className="font-medium">{Math.round(Number(portfolioSummary.portfolio_score))}</span>
                  </span>
                )}
                {propertiesAtRisk > 0 && (
                  <span className="text-amber-800 font-medium">
                    {propertiesAtRisk} with elevated compliance risk
                  </span>
                )}
              </div>
              {portfolioSummary.kpis && (
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-gray-700">
                  {portfolioSummary.kpis.compliant != null && <span>Compliant: {portfolioSummary.kpis.compliant}</span>}
                  {portfolioSummary.kpis.overdue != null && <span>Overdue: {portfolioSummary.kpis.overdue}</span>}
                  {portfolioSummary.kpis.expiring_30 != null && (
                    <span>Expiring (30d): {portfolioSummary.kpis.expiring_30}</span>
                  )}
                  {portfolioSummary.kpis.missing != null && <span>Missing: {portfolioSummary.kpis.missing}</span>}
                </div>
              )}
              {portfolioSummary.updated_at && (
                <p className="text-xs text-gray-500">
                  Updated {new Date(portfolioSummary.updated_at).toLocaleString()}
                </p>
              )}
              <Button variant="link" className="h-auto p-0 text-electric-teal" asChild>
                <Link to="/requirements">
                  Requirements <ChevronRight className="inline h-4 w-4" aria-hidden />
                </Link>
              </Button>
            </>
          ) : (
            <p className="text-gray-600">Portfolio summary is not available.</p>
          )}
        </CardContent>
      </Card>

      {/* 4. Jobs — prioritized + stuck signals */}
      <Card className="mb-6 border border-gray-200 shadow-sm" data-testid="command-center-jobs">
        <CardHeader className="pb-2 flex flex-row items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Wrench className="h-4 w-4 text-teal-600" />
              Jobs that need attention
            </CardTitle>
            <p className="text-xs text-gray-500 mt-1 font-normal">
              Ranked by SLA risk, holds, proof, and contractor waits—then due dates.
            </p>
          </div>
          {maintenanceEnabled && (
            <Button variant="outline" size="sm" className="shrink-0" asChild>
              <Link to="/operations/work-orders">All jobs</Link>
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {!maintenanceEnabled && (
            <p className="text-sm text-gray-600">
              Job tracking is not enabled for your plan. Upgrade to see maintenance workflows.
            </p>
          )}
          {maintenanceEnabled && workOrdersRaw === null && !error && (
            <p className="text-sm text-gray-600">Could not load jobs.</p>
          )}
          {maintenanceEnabled && workOrdersRaw && (
            <>
              {(jobSignals.awaitingProof > 0 ||
                jobSignals.onHoldOrParts > 0 ||
                jobSignals.pendingContractor > 0) && (
                <div
                  className="flex flex-wrap gap-2 text-xs sm:text-sm"
                  data-testid="command-center-job-signals"
                >
                  {jobSignals.awaitingProof > 0 && (
                    <span className="inline-flex items-center rounded-full bg-violet-100 text-violet-900 px-2.5 py-1 font-medium">
                      {jobSignals.awaitingProof} awaiting proof
                    </span>
                  )}
                  {jobSignals.onHoldOrParts > 0 && (
                    <span className="inline-flex items-center rounded-full bg-slate-200 text-slate-900 px-2.5 py-1 font-medium">
                      {jobSignals.onHoldOrParts} on hold / awaiting parts
                    </span>
                  )}
                  {jobSignals.pendingContractor > 0 && (
                    <span className="inline-flex items-center rounded-full bg-sky-100 text-sky-900 px-2.5 py-1 font-medium">
                      {jobSignals.pendingContractor} with contractor
                    </span>
                  )}
                </div>
              )}

              {rankedJobs.length === 0 && calmSnapshot && (
                <p className="text-sm text-gray-700">
                  <span className="font-medium text-green-800">All active jobs are under control</span>—none in this
                  snapshot. Open Jobs if you need the full execution list.
                </p>
              )}
              {rankedJobs.length === 0 && !calmSnapshot && (
                <p className="text-sm text-gray-600">No active jobs. Open Jobs for completed history and filters.</p>
              )}
              {rankedJobs.length > 0 && (
                <ul className="space-y-3 text-sm">
                  {rankedJobs.map((wo) => {
                    const badge = attentionBadgeForJob(wo);
                    const jobTitle = (() => {
                      const d = String(wo.description || wo.title || '').trim();
                      if (d) return d;
                      const rt = wo.requirement_type || wo.compliance_requirement_type;
                      if (rt) return requirementLabel(rt);
                      return 'Job';
                    })();
                    const propLbl = wo.property_id ? propertyLabelById.get(wo.property_id) : null;
                    return (
                      <li
                        key={wo.work_order_id}
                        className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-gray-100 pb-3 last:border-0 last:pb-0"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              className="text-left font-medium text-midnight-blue hover:underline break-words"
                              onClick={() =>
                                navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)
                              }
                            >
                              {jobTitle}
                            </button>
                            {badge && (
                              <span
                                className={`inline-flex text-xs font-medium px-2 py-0.5 rounded ${badge.className}`}
                              >
                                {badge.label}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {workOrderKindClientLabel(wo)}
                            {' · '}
                            {workOrderStatusLabel(wo.status)}
                            {propLbl ? ` · ${propLbl}` : ''}
                          </p>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          className="shrink-0 w-full sm:w-auto"
                          onClick={() => navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)}
                        >
                          Manage job
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
