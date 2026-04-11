/**
 * Client Command Center — single screen: synthesized verdict, compliance, priority snapshot,
 * portfolio summary, and jobs ranked by operational importance (existing APIs only).
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { workOrderStatusLabel } from '../domain/presentDomain';
import {
  workOrderKindClientLabel,
  clientInboxJobCtaLabel,
  CLIENT_INBOX_JOB_FALLBACK_CTA,
} from '../utils/jobWorkflowUi';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import {
  aggregateJobSignals,
  attentionBadgeForJob,
  buildCommandCenterVerdict,
  buildPortfolioVerdictBlock,
  buildPropertyPriorityRepresentatives,
  commandCenterWhyThisMattersLine,
  computePortfolioDriverMetrics,
  countPropertiesAtRisk,
  hasTruthyIso,
  isActiveWorkOrder,
  isAwaitingProof,
  isCommandCenterAllClearEmpty,
  isCommandCenterCalmSnapshot,
  isOperationalHold,
  rankWorkOrdersByAttention,
  sanitizeCommandCenterCtaLabel,
  buildCommandCenterPropertyRowHubLink,
  commandCenterJobRowHeadline,
} from '../utils/clientCommandCenter';
import { COMMAND_CENTER_CONFIDENCE_LINE } from '../utils/confidenceUxCopy';

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

  const reloadBundle = useCallback(() => {
    if (!isClientUser) return;
    const maintenanceEnabled = hasFeature('maintenance_workflows');
    const tasks = [
      clientAPI.getCommandCenter({}).then((r) => r.data),
      clientAPI.getComplianceSummary().then((r) => r.data),
    ];
    if (maintenanceEnabled) {
      tasks.push(clientAPI.getMaintenanceWorkOrders({ skip: 0, limit: 200 }).then((r) => r.data));
    }
    Promise.all(tasks.map((p) => p.then((data) => ({ ok: true, data })).catch(() => ({ ok: false })))).then((results) => {
      const [ccRes, psRes, woRes] = maintenanceEnabled ? results : [...results, { ok: false }];
      if (ccRes.ok && ccRes.data) setBundle(ccRes.data);
      if (psRes.ok && psRes.data) setPortfolioSummary(psRes.data);
      if (maintenanceEnabled && woRes?.ok && woRes.data) setWorkOrdersRaw(woRes.data);
    });
  }, [isClientUser, hasFeature]);

  useEffect(() => {
    if (!isClientUser) return undefined;
    const onOutcome = () => {
      reloadBundle();
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') reloadBundle();
    };
    window.addEventListener('compliance-outcome', onOutcome);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('compliance-outcome', onOutcome);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [isClientUser, reloadBundle]);

  const urgentCount = bundle?.urgent_actions?.length ?? 0;
  const propertyPriorityReps = useMemo(
    () => buildPropertyPriorityRepresentatives(bundle?.urgent_actions || [], 8),
    [bundle?.urgent_actions]
  );
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

  const portfolioVerdict = useMemo(() => {
    const actions = bundle?.urgent_actions || [];
    return buildPortfolioVerdictBlock({
      summary,
      portfolioSummary,
      urgentCount: actions.length,
      urgentActions: actions,
      riskCount,
      predictiveEnabled,
      breachedJobCount,
      blockedJobCount,
      awaitingProofJobCount: awaitingProofJobCount,
    });
  }, [
    bundle?.urgent_actions,
    summary,
    portfolioSummary,
    riskCount,
    predictiveEnabled,
    breachedJobCount,
    blockedJobCount,
    awaitingProofJobCount,
  ]);

  const pressureMetrics = useMemo(
    () =>
      computePortfolioDriverMetrics({
        summary,
        portfolioSummary,
        urgentActions: bundle?.urgent_actions || [],
        breachedJobCount,
        blockedJobCount,
        awaitingProofJobCount,
      }),
    [
      summary,
      portfolioSummary,
      bundle?.urgent_actions,
      breachedJobCount,
      blockedJobCount,
      awaitingProofJobCount,
    ]
  );

  const prevPressureRef = useRef(null);
  const [improvedFlash, setImprovedFlash] = useState({
    overdue: false,
    missing: false,
    jobs: false,
  });

  useEffect(() => {
    if (loading) return;
    const prev = prevPressureRef.current;
    const cur = pressureMetrics;
    if (prev) {
      const next = { overdue: false, missing: false, jobs: false };
      let any = false;
      if (cur.overdueDisplay < prev.overdueDisplay) {
        next.overdue = true;
        any = true;
      }
      if (cur.missingDisplay < prev.missingDisplay) {
        next.missing = true;
        any = true;
      }
      if (cur.jobPressure < prev.jobPressure) {
        next.jobs = true;
        any = true;
      }
      if (any) {
        setImprovedFlash(next);
        const t = window.setTimeout(
          () => setImprovedFlash({ overdue: false, missing: false, jobs: false }),
          1700
        );
        prevPressureRef.current = cur;
        return () => window.clearTimeout(t);
      }
    }
    prevPressureRef.current = cur;
  }, [loading, pressureMetrics]);

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
            Portfolio synthesis and prioritisation—execution stays in Today, Jobs, Requirements, and Documents. Use the
            status block below to pick your next step.
          </p>
          <p className="text-sm text-gray-600 mt-2">{COMMAND_CENTER_CONFIDENCE_LINE}</p>
        </div>
        <div className="shrink-0 flex flex-col gap-2 items-start sm:items-end">
          <Link
            to="/today"
            className="text-sm font-semibold text-electric-teal hover:underline inline-flex items-center gap-1"
            data-testid="command-center-link-today"
          >
            Open Today inbox
            <ChevronRight className="h-4 w-4" aria-hidden />
          </Link>
          <div className="flex flex-wrap gap-x-3 gap-y-1 justify-start sm:justify-end text-xs text-gray-500">
            <Link to="/reports" className="hover:text-midnight-blue hover:underline" data-testid="command-center-link-reports">
              Compliance report
            </Link>
            <span className="text-gray-300" aria-hidden>
              ·
            </span>
            <Link to="/dashboard" className="hover:text-midnight-blue hover:underline" data-testid="command-center-link-dashboard">
              Dashboard
            </Link>
          </div>
        </div>
      </div>

      <ErrorBanner message={error} />

      {/* Portfolio verdict + synthesis */}
      <div
        className={`mb-6 rounded-xl border px-4 py-4 sm:px-5 sm:py-5 ${verdictBannerClasses(portfolioVerdict.statusTone)}`}
        data-testid="command-center-verdict"
        role="status"
      >
        <div data-testid="command-center-portfolio-verdict">
          <p className="text-xs font-semibold uppercase tracking-wide opacity-80">Portfolio status</p>
          <p className="text-lg font-semibold leading-snug mt-1">{portfolioVerdict.statusLabel}</p>
          {portfolioVerdict.drivers.length > 0 ? (
            <div className="mt-3">
              <p className="text-xs font-semibold uppercase tracking-wide opacity-80">What needs attention</p>
              <ul className="mt-2 list-disc list-inside text-sm space-y-1 opacity-95">
                {portfolioVerdict.drivers.map((d) => {
                  const flashDriver =
                    (d.key === 'overdue' && improvedFlash.overdue) ||
                    (d.key === 'missing' && improvedFlash.missing) ||
                    (d.key === 'job_pressure' && improvedFlash.jobs);
                  return (
                    <li
                      key={d.key}
                      className={
                        flashDriver
                          ? 'rounded px-1 -mx-1 -my-0.5 py-0.5 command-center-metric-improved'
                          : undefined
                      }
                    >
                      {d.label}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : portfolioVerdict.driverSummaryFallback ? (
            <p className="text-sm mt-3 opacity-90">{portfolioVerdict.driverSummaryFallback}</p>
          ) : null}
          <div className="mt-4 pt-3 border-t border-black/5">
            <p className="text-xs font-semibold uppercase tracking-wide opacity-80">What to do next</p>
            <p className="text-sm mt-1 font-medium">{portfolioVerdict.bestNextMove}</p>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center mt-3">
              <Button size="sm" className="bg-midnight-blue hover:bg-midnight-blue/90 w-full sm:w-auto" asChild>
                <Link to={portfolioVerdict.nextHintPath}>{portfolioVerdict.nextHintLabel}</Link>
              </Button>
              {portfolioVerdict.verdictSecondaryNav ? (
                <Link
                  to={portfolioVerdict.verdictSecondaryNav.path}
                  className="text-xs text-gray-600 hover:text-midnight-blue hover:underline sm:ml-1"
                >
                  {portfolioVerdict.verdictSecondaryNav.label}
                </Link>
              ) : null}
            </div>
          </div>
        </div>
        <p className="text-sm mt-4 pt-3 border-t border-black/5 opacity-90">{verdict.line}</p>
        {verdict.subline ? <p className="text-sm mt-2 opacity-85">{verdict.subline}</p> : null}
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
                No urgent actions, no major risks in this snapshot, and no active jobs. Continue in Today when you are ready
                for the next inbox item.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 1. Status summary */}
      <Card className="mb-6 border border-gray-200 shadow-sm" data-testid="command-center-status">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Compliance &amp; issues</CardTitle>
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
                {summary.requirements_overdue != null && (
                  <span
                    className={
                      improvedFlash.overdue
                        ? 'inline-block rounded-sm px-1 -mx-0.5 command-center-metric-improved'
                        : undefined
                    }
                  >
                    Overdue: {summary.requirements_overdue}
                  </span>
                )}
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
                <Link to="/operations/risk-signals">Review flagged issues</Link>
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 2. Property-first priorities (synthesis — execution stays in Today) */}
      <Card className="mb-6 border border-gray-200 shadow-sm" data-testid="command-center-urgent">
        <CardHeader className="pb-2 flex flex-row items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-teal-600" />
              Where to focus first
            </CardTitle>
            <p className="text-xs text-gray-500 mt-1 font-normal">
              One primary action per property; Open property and the extra link are for context only.
            </p>
          </div>
        </CardHeader>
        <CardContent>
          {propertyPriorityReps.length > 0 ? (
            <ul className="space-y-4 text-sm" data-testid="command-center-property-priorities">
              {propertyPriorityReps.map((t, idx) => {
                const propName =
                  (t.property_id && propertyLabelById.get(t.property_id)) ||
                  String(t.property_label || '').trim() ||
                  'Property';
                const whyMatters = commandCenterWhyThisMattersLine(t);
                const cta = sanitizeCommandCenterCtaLabel(t.primary_action_label, t);
                const primaryResolved = resolveClientPortalPath(
                  resolveTaskCta(t, 'primary').route || '/today',
                  '/today',
                );
                const hub = buildCommandCenterPropertyRowHubLink(t, primaryResolved);
                return (
                  <li
                    key={t.property_id || t.id || idx}
                    className="border-b border-gray-100 pb-4 last:border-0 last:pb-0"
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                      <div className="flex gap-2 min-w-0 flex-1">
                        <span className="text-xs font-semibold text-gray-400 w-5 shrink-0 pt-0.5">{idx + 1}.</span>
                        <div className="min-w-0 space-y-1">
                          <p className="font-semibold text-midnight-blue break-words">{propName}</p>
                          <p className="text-sm text-gray-800 break-words">{whyMatters}</p>
                        </div>
                      </div>
                      <div className="flex flex-col gap-2 shrink-0 sm:items-end pl-7 sm:pl-0 w-full sm:w-auto">
                        <Button
                          type="button"
                          size="sm"
                          className="w-full sm:w-auto bg-midnight-blue hover:bg-midnight-blue/90"
                          onClick={() => onUrgentClick(t)}
                        >
                          {cta}
                        </Button>
                        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs justify-end text-gray-500">
                          {t.property_id ? (
                            <Link
                              className="font-medium hover:text-midnight-blue hover:underline"
                              to={`/properties/${encodeURIComponent(t.property_id)}`}
                            >
                              Open property
                            </Link>
                          ) : null}
                          {hub ? (
                            <Link className="font-medium hover:text-midnight-blue hover:underline" to={hub.to}>
                              {hub.label}
                            </Link>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : urgentCount > 0 ? (
            <p className="text-sm text-gray-600">
              Items in your queue are not tied to a property in this snapshot.{' '}
              <Link className="text-electric-teal font-medium hover:underline" to="/today">
                Continue in Today
              </Link>{' '}
              and resolve them in order.
            </p>
          ) : calmSnapshot ? (
            <p className="text-sm text-gray-700">
              <span className="font-medium text-green-800">No property-level priorities in this snapshot.</span> Continue
              in Today for scheduled or lower-priority inbox work.
            </p>
          ) : (
            <p className="text-sm text-gray-600">
              No property-level priorities in this snapshot — continue in Today for the full task list, snooze, and dismiss.
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
                  {portfolioSummary.kpis.overdue != null && (
                    <span
                      className={
                        improvedFlash.overdue
                          ? 'inline-block rounded-sm px-1 -mx-0.5 command-center-metric-improved'
                          : undefined
                      }
                    >
                      Overdue: {portfolioSummary.kpis.overdue}
                    </span>
                  )}
                  {portfolioSummary.kpis.expiring_30 != null && (
                    <span>Expiring (30d): {portfolioSummary.kpis.expiring_30}</span>
                  )}
                  {portfolioSummary.kpis.missing != null && (
                    <span
                      className={
                        improvedFlash.missing
                          ? 'inline-block rounded-sm px-1 -mx-0.5 command-center-metric-improved'
                          : undefined
                      }
                    >
                      Missing: {portfolioSummary.kpis.missing}
                    </span>
                  )}
                </div>
              )}
              {portfolioSummary.updated_at && (
                <p className="text-xs text-gray-500">
                  Updated {new Date(portfolioSummary.updated_at).toLocaleString()}
                </p>
              )}
              <Button variant="link" className="h-auto p-0 text-electric-teal" asChild>
                <Link to="/requirements">
                  Review requirements <ChevronRight className="inline h-4 w-4" aria-hidden />
                </Link>
              </Button>
            </>
          ) : (
            <p className="text-gray-600">Portfolio summary is not available.</p>
          )}
        </CardContent>
      </Card>

      {/* 4. Jobs — ranked attention list */}
      <Card
        className="mb-6 border border-dashed border-gray-200 bg-slate-50/50 shadow-none text-gray-800"
        data-testid="command-center-jobs"
      >
        <CardHeader className="pb-2 flex flex-row items-start justify-between gap-2">
          <div>
            <CardTitle className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Wrench className="h-4 w-4 text-gray-500" />
              Jobs that need attention
            </CardTitle>
            <p className="text-xs text-gray-500 mt-1 font-normal">
              Below the property list — same jobs, short headlines, ranked by urgency.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-0">
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
                  className={
                    improvedFlash.jobs
                      ? 'command-center-metric-improved flex flex-wrap gap-2 text-xs sm:text-sm rounded-lg px-1 py-1 -mx-1 -my-1'
                      : 'flex flex-wrap gap-2 text-xs sm:text-sm'
                  }
                  data-testid="command-center-job-signals"
                >
                  {jobSignals.awaitingProof > 0 && (
                    <span className="inline-flex items-center rounded-full bg-violet-100 text-violet-900 px-2.5 py-1 font-medium">
                      {jobSignals.awaitingProof} awaiting proof
                    </span>
                  )}
                  {jobSignals.onHoldOrParts > 0 && (
                    <span className="inline-flex items-center rounded-full bg-slate-200 text-slate-900 px-2.5 py-1 font-medium">
                      {jobSignals.onHoldOrParts} operationally paused
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
                  <span className="font-medium text-green-800">All active jobs look under control</span> in this
                  snapshot. Use “What to do next” or Jobs when you need the full queue.
                </p>
              )}
              {rankedJobs.length === 0 && !calmSnapshot && (
                <p className="text-sm text-gray-600">
                  No active jobs here — open Jobs for history and filters.
                </p>
              )}
              {rankedJobs.length > 0 && (
                <ul className="space-y-3 text-sm">
                  {rankedJobs.map((wo) => {
                    const badge = attentionBadgeForJob(wo);
                    const jobTitle = commandCenterJobRowHeadline(wo);
                    const propLbl = wo.property_id ? propertyLabelById.get(wo.property_id) : null;
                    return (
                      <li
                        key={wo.work_order_id}
                        className="flex flex-col gap-2 border-b border-gray-100 pb-3 last:border-0 last:pb-0"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-medium text-midnight-blue break-words">{jobTitle}</p>
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
                        <div>
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-full sm:w-auto text-xs h-8 border-gray-300 text-gray-700"
                            onClick={() => navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)}
                          >
                            {clientInboxJobCtaLabel({ ...wo, source_type: 'work_order' }) ||
                              CLIENT_INBOX_JOB_FALLBACK_CTA}
                          </Button>
                        </div>
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
