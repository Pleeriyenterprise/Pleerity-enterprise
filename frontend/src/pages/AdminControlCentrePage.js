import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CreditCard,
  Gauge,
  RefreshCw,
  Shield,
  Users,
  Zap,
} from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import {
  complianceScoreBandLabel,
  complianceStatusBucketLabel,
  displayJobName,
  humanizeScoringNoteKey,
  humanizeScoringNoteText,
  overallAutomationHealthLabel,
  threatDetectionsRawJson,
  threatDetectionsToDisplayRows,
} from '../utils/controlCentrePresentation';

function formatGbpPence(pence) {
  if (pence == null || Number.isNaN(Number(pence))) return '—';
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(Number(pence) / 100);
}

function StatusPill({ status }) {
  const s = (status || '').toLowerCase();
  const cls =
    s === 'critical'
      ? 'bg-red-100 text-red-900 border-red-200'
      : s === 'degraded'
        ? 'bg-amber-100 text-amber-900 border-amber-200'
        : 'bg-emerald-100 text-emerald-900 border-emerald-200';
  const label = s === 'critical' ? 'Critical' : s === 'degraded' ? 'Degraded' : 'Healthy';
  return <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-sm font-semibold border ${cls}`}>{label}</span>;
}

function ScoreCard({ title, value, hint, invert }) {
  const v = value == null ? null : Number(value);
  const color =
    v == null
      ? 'text-gray-400'
      : invert
        ? v > 60
          ? 'text-red-700'
          : v > 35
            ? 'text-amber-700'
            : 'text-emerald-700'
        : v < 40
          ? 'text-red-700'
          : v < 70
            ? 'text-amber-700'
            : 'text-emerald-700';
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">{title}</div>
      <div className={`mt-1 text-3xl font-bold tabular-nums ${color}`}>{v != null ? v : '—'}</div>
      {hint ? <div className="mt-2 text-xs text-gray-500">{hint}</div> : null}
    </div>
  );
}

function MetricGrid({ items }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {items.map(([label, val]) => (
        <div key={label} className="bg-gray-50 border border-gray-100 rounded-md p-3">
          <div className="text-xs text-gray-500">{label}</div>
          <div className="mt-1 text-lg font-semibold text-gray-900 break-words">{val}</div>
        </div>
      ))}
    </div>
  );
}

const CONTROL_CENTRE_POLL_MS = Number(process.env.REACT_APP_CONTROL_CENTRE_POLL_MS) || 30000;

export default function AdminControlCentrePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getControlCentreSnapshot();
      setData(res?.data || null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load Control Centre');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const t = setInterval(load, CONTROL_CENTRE_POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const sys = data?.system;
  const auto = data?.automation;
  const sec = data?.security;
  const rev = data?.revenue;
  const eng = data?.engagement;
  const alerts = data?.alerts || [];
  const revenueVisible = data?.access?.revenue_visible === true;
  const secInc = sec?.summary?.incidents;

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Gauge className="w-8 h-8 text-indigo-600" />
              Platform status
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              Cross-cutting snapshot: health, automation, security, engagement, and revenue signals. Polling ~{Math.round(CONTROL_CENTRE_POLL_MS / 1000)}s plus manual refresh. Revenue metrics and revenue health score are visible only to{' '}
              <span className="font-medium">Owner</span> (ROLE_OWNER). Overall status does not penalize non-owners for hidden revenue data.
            </p>
            {data?.generated_at ? (
              <p className="text-xs text-gray-500 mt-1">Last built: {new Date(data.generated_at).toLocaleString()}</p>
            ) : null}
          </div>
          <div className="flex items-center gap-3">
            <StatusPill status={sys?.status} />
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw className={loading ? 'w-4 h-4 animate-spin' : 'w-4 h-4'} />
              Refresh
            </button>
          </div>
        </div>

        {sys ? (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Activity className="w-5 h-5" />
              System health layer
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              <ScoreCard title="Automation health" value={sys.scores?.automation_health} hint="100 = best; from job failures, SLA, heartbeat, incidents." />
              <ScoreCard title="Security risk" value={sys.scores?.security_risk} hint="0 = best; higher = more flagged issues." invert />
              <ScoreCard
                title="Revenue health"
                value={sys.scores?.revenue_health}
                hint={
                  revenueVisible
                    ? '100 = best; from past-due accounts, failed payments, and entitlement limits (heuristic).'
                    : 'Owner-only. Not shown for your role; excluded from your status penalty.'
                }
              />
              <ScoreCard title="Job confidence" value={sys.scores?.job_confidence} hint="Derived from critical job states." />
            </div>
            <div className="text-sm text-gray-600 bg-slate-50 border border-slate-100 rounded-lg p-3">
              <span className="font-medium text-gray-800">Automation engine status:</span>{' '}
              <span className="text-gray-900">{overallAutomationHealthLabel(sys.overall_automation_health)}</span>
              <details className="mt-2 text-xs">
                <summary
                  className="cursor-pointer text-indigo-600 hover:underline select-none"
                  data-testid="automation-engine-tech-details"
                >
                  Technical details
                </summary>
                <div className="mt-2 rounded border border-slate-200 bg-white p-2 font-mono text-[11px] text-slate-700 space-y-1">
                  <div>
                    <span className="text-slate-500">overall_automation_health:</span> {String(sys.overall_automation_health ?? '—')}
                  </div>
                  {sys.observability_db_name ? (
                    <div>
                      <span className="text-slate-500">Observability DB:</span> {sys.observability_db_name}
                    </div>
                  ) : null}
                </div>
              </details>
              <div className="mt-2 text-xs text-gray-500">
                Last check timestamp (snapshot build):{' '}
                {sys.last_system_check_at ? new Date(sys.last_system_check_at).toLocaleString() : '—'}.
                {sys.revenue_excluded_from_status_when_redacted ? (
                  <span className="block mt-1 text-indigo-700">
                    Revenue signals are hidden for your role; automation + security still drive overall status.
                  </span>
                ) : null}
              </div>
            </div>
          </section>
        ) : null}

        {auto ? (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-600" />
              Automation
            </h2>
            <MetricGrid
              items={[
                ['Tracked critical jobs', String(auto.total_tracked_jobs ?? '—')],
                ['Total job run records (DB)', String(auto.total_job_runs_recorded ?? '—')],
                ['Healthy (critical)', String(auto.healthy_critical_jobs ?? '—')],
                ['Failed (critical)', String(auto.failed_critical_jobs ?? '—')],
                ['Degraded (critical)', String(auto.degraded_critical_jobs ?? '—')],
                ['Missed (critical)', String(auto.missed_critical_jobs ?? '—')],
                ['Never ran / overdue (critical)', String(auto.never_ran_overdue_critical_jobs ?? '—')],
                ['Failed runs (24h)', String(auto.failed_runs_24h ?? '—')],
                ['Degraded runs (24h)', String(auto.degraded_runs_24h ?? '—')],
                [
                  'Last completed (sample)',
                  auto.last_completed_latest_critical_path
                    ? new Date(auto.last_completed_latest_critical_path).toLocaleString()
                    : '—',
                ],
                [
                  'Next run (earliest shown)',
                  auto.next_scheduled_run_earliest ? new Date(auto.next_scheduled_run_earliest).toLocaleString() : '—',
                ],
                ['Open operational incidents', String(auto.open_operational_incidents ?? '—')],
              ]}
            />
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="font-medium text-gray-900 mb-2">Automation outcome tallies (24h)</h3>
              <p className="text-xs text-gray-500 mb-3">
                Sums of per-run outcome counters across all finished jobs in the window. Different job types use these fields
                differently — interpret as operational volume, not a single business result. Use Automation Centre for per-job
                detail.
              </p>
              <MetricGrid
                items={[
                  ['Finished runs', String(auto.business_outcomes_24h?.finished_runs ?? '—')],
                  ['Successful units (summed)', String(auto.business_outcomes_24h?.outcome_success_sum ?? '—')],
                  ['Failed units (summed)', String(auto.business_outcomes_24h?.outcome_failed_sum ?? '—')],
                  ['Attempted units (summed)', String(auto.business_outcomes_24h?.outcome_attempted_sum ?? '—')],
                ]}
              />
            </div>
            {(auto.jobs_flagged_no_expected_outcome || []).length > 0 ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
                <div className="font-semibold text-amber-900 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  Jobs that reported success but produced no attempted outcomes (unexpected for this job class)
                </div>
                <ul className="mt-2 list-disc list-inside text-amber-900 space-y-2" data-testid="control-centre-jobs-flagged">
                  {auto.jobs_flagged_no_expected_outcome.map((j) => (
                    <li key={j.job_name}>
                      <span className="font-medium text-amber-950" data-testid={`job-flag-title-${j.job_name}`}>
                        {displayJobName(j.job_name)}
                      </span>
                      <span className="text-amber-900"> — {j.recommended_action}</span>
                      <details className="mt-1 ml-4 text-xs text-amber-800">
                        <summary className="cursor-pointer hover:underline select-none">Technical id</summary>
                        <code className="mt-1 block rounded bg-amber-100/80 px-1.5 py-0.5 text-[11px]">{j.job_name}</code>
                      </details>
                    </li>
                  ))}
                </ul>
                <Link to="/admin/automation" className="inline-block mt-2 text-indigo-700 font-medium text-sm hover:underline">
                  Open Automation Centre →
                </Link>
              </div>
            ) : (
              <p className="text-sm text-gray-500 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                No jobs flagged for “success with zero attempted outcomes” in the latest critical-path sample.
              </p>
            )}
          </section>
        ) : null}

        {sec?.summary ? (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-600" />
              Security
            </h2>
            <MetricGrid
              items={[
                ['Failed login attempts (7d window)', String(sec.failed_login_attempts_7d ?? '—')],
                ['Open security incidents', String(sec.suspicious_activity?.open_security_incidents ?? '—')],
                ['Webhook validation failures (7d)', String(sec.webhook_validation_failures_7d ?? '—')],
                ['Token misuse events (7d)', String(sec.token_misuse_7d ?? '—')],
                ['Document access violations (7d)', String(sec.document_access_violations_7d ?? '—')],
                ['Cross-user access attempts (7d)', String(sec.suspicious_activity?.cross_user_access_attempts_7d ?? '—')],
                ['Security incidents resolved (7d)', String(sec.security_incidents_resolved_7d ?? '—')],
              ]}
            />
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="font-medium text-gray-900 mb-2">Threat-type incident counts (7d)</h3>
              <p className="text-xs text-gray-500 mb-3">
                From security incident records aggregated by type. Non-zero rows warrant review in Security Monitoring.
              </p>
              <div data-testid="control-centre-threat-summary">
                <MetricGrid items={threatDetectionsToDisplayRows(sec.suspicious_activity?.threat_detections_7d)} />
              </div>
              <details className="mt-3 text-xs">
                <summary className="cursor-pointer text-indigo-600 hover:underline select-none">Technical details (raw keys)</summary>
                <pre
                  data-testid="control-centre-threat-raw-json"
                  className="mt-2 max-h-40 overflow-auto rounded border border-slate-200 bg-slate-50 p-2 font-mono text-[11px] text-slate-700 whitespace-pre-wrap"
                >
                  {threatDetectionsRawJson(sec.suspicious_activity?.threat_detections_7d)}
                </pre>
              </details>
            </div>
            {secInc?.recent_truncated ? (
              <p className="text-xs text-gray-500">
                Security incident list truncated for payload ({secInc.recent_omitted_count ?? 0} omitted). Open Security Monitoring for the full list.
              </p>
            ) : null}
            <Link to="/admin/security" className="text-indigo-600 font-medium text-sm hover:underline">
              Security Monitoring →
            </Link>
          </section>
        ) : null}

        {rev?.redacted ? (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-gray-400" />
              Revenue
            </h2>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-800">{rev.reason}</div>
          </section>
        ) : rev ? (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-emerald-700" />
              Revenue
            </h2>
            <MetricGrid
              items={[
                ['Revenue today', formatGbpPence(rev.revenue_today_pence)],
                ['Revenue this month', formatGbpPence(rev.revenue_this_month_pence)],
                ['Paid charges today', String(rev.paid_charges_today_count ?? '—')],
                ['Paid charges (month)', String(rev.paid_charges_month_count ?? '—')],
                ['Active subscriptions (billing)', String(rev.active_subscriptions ?? '—')],
                ['MRR (plan table)', formatGbpPence(rev.mrr_pence)],
                ['Failed payments (30d)', String(rev.failed_payments_30d ?? '—')],
                ['Past-due accounts', String(rev.past_due_accounts ?? '—')],
                ['Pending invoices (ops)', String(rev.pending_invoices ?? '—')],
                ['Revenue at risk (MRR heuristic)', formatGbpPence(rev.revenue_at_risk_pence)],
                ['LIMITED entitlement clients', String(rev.limited_entitlement_clients ?? '—')],
                ['Stripe events FAILED (3d)', String(rev.stripe_events_failed_recent ?? '—')],
              ]}
            />
            {rev.revenue_at_risk_note ? <p className="text-xs text-gray-500">{rev.revenue_at_risk_note}</p> : null}
            <p className="text-xs text-gray-500">
              Paid revenue sums use aggregation with normalized <code className="text-xs">created_at</code> (date or ISO string).
            </p>
            <Link to="/admin/billing" className="text-indigo-600 font-medium text-sm hover:underline">
              Billing →
            </Link>
          </section>
        ) : null}

        {eng ? (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Users className="w-5 h-5 text-sky-600" />
              Users & engagement
            </h2>
            <MetricGrid
              items={[
                ['New clients (7d)', String(eng.new_clients_7d ?? '—')],
                ['Provisioned clients (activated onboarding)', String(eng.provisioned_clients_total ?? '—')],
                ['Portal users (client roles, active)', String(eng.portal_users_active_client_roles ?? '—')],
                ['Inactive portal users (30d, client roles)', String(eng.portal_users_inactive_30d_client_roles ?? '—')],
                ['Onboarding completion rate', `${eng.onboarding_completion_rate_percent ?? '—'}%`],
                ['Document uploads (7d)', String(eng.document_uploads_7d ?? '—')],
                ['Properties in compliance snapshot', String(eng.total_properties_scored ?? '—')],
              ]}
            />
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="font-medium text-gray-900 mb-2">Compliance status (properties)</h3>
              <p className="text-xs text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-2 py-1.5 mb-3">
                <strong>Non-authoritative DB snapshot:</strong> counts come from stored property rows in the database, not the
                live client compliance headline or Stream B score authority. Use tenant compliance views and score tooling
                for authoritative posture.
              </p>
              <MetricGrid
                items={Object.entries(eng.compliance_status_by_property || {}).map(([k, v]) => [
                  complianceStatusBucketLabel(k),
                  String(v),
                ])}
              />
            </div>
            {eng.compliance_numeric_score_buckets ? (
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 mb-2">Numeric compliance score bands (properties)</h3>
                <p className="text-xs text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-2 py-1.5 mb-2">
                  Same snapshot caveat: persisted <code className="text-[10px]">compliance_score</code> on property documents
                  only — not a substitute for portal headline or recalculation state.
                </p>
                <MetricGrid
                  items={Object.entries(eng.compliance_numeric_score_buckets).map(([k, v]) => [
                    complianceScoreBandLabel(k),
                    String(v),
                  ])}
                />
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
            Incidents & alerts
          </h2>
          {alerts.length === 0 ? (
            <p className="text-sm text-gray-500">No central alerts for current thresholds.</p>
          ) : (
            <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">Severity</th>
                    <th className="px-3 py-2 text-left">Category</th>
                    <th className="px-3 py-2 text-left">Title</th>
                    <th className="px-3 py-2 text-left">Status</th>
                    <th className="px-3 py-2 text-left">When</th>
                    <th className="px-3 py-2 text-left">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {alerts.map((a) => (
                    <tr key={a.id}>
                      <td className="px-3 py-2 font-medium">{a.severity}</td>
                      <td className="px-3 py-2">{a.category}</td>
                      <td className="px-3 py-2 max-w-md">
                        <div className="font-medium text-gray-900">{a.title}</div>
                        {a.metadata?.threat_detections && typeof a.metadata.threat_detections === 'object' ? (
                          <div className="text-gray-600 text-xs mt-0.5 space-y-1">
                            <p className="line-clamp-3">Aggregated counts by threat type (see Security section for full table).</p>
                            <ul className="list-disc list-inside text-[11px]">
                              {threatDetectionsToDisplayRows(a.metadata.threat_detections)
                                .filter((row) => row[1] !== '0' || String(row[0]).startsWith('No threat'))
                                .slice(0, 8)
                                .map((row) => (
                                  <li key={`${a.id}-${row[0]}`}>
                                    {row[0]}: {row[1]}
                                  </li>
                                ))}
                            </ul>
                            <details className="text-[11px]">
                              <summary className="cursor-pointer text-indigo-600">Raw alert detail</summary>
                              <pre className="mt-1 max-h-24 overflow-auto rounded bg-slate-50 p-1 font-mono whitespace-pre-wrap">
                                {a.detail}
                              </pre>
                            </details>
                          </div>
                        ) : (
                          <div className="text-gray-600 text-xs mt-0.5 line-clamp-2">{a.detail}</div>
                        )}
                        {a.metadata?.related_job_name ? (
                          <div className="text-[11px] text-gray-500 mt-1">
                            <span>Related automation: </span>
                            <span className="font-medium text-gray-700">{displayJobName(a.metadata.related_job_name)}</span>
                            <details className="mt-0.5">
                              <summary className="cursor-pointer text-indigo-600">Technical job id</summary>
                              <code className="mt-1 block text-[10px] font-mono bg-slate-50 rounded px-1 py-0.5">
                                {a.metadata.related_job_name}
                              </code>
                            </details>
                          </div>
                        ) : null}
                      </td>
                      <td className="px-3 py-2">{a.status}</td>
                      <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                        {a.timestamp ? new Date(a.timestamp).toLocaleString() : '—'}
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-700 max-w-xs">
                        <div>{a.required_action}</div>
                        {a.link_path ? (
                          <Link to={a.link_path} className="text-indigo-600 font-medium mt-1 inline-block hover:underline">
                            Open →
                          </Link>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {data?.scoring_notes ? (
          <section className="text-xs text-gray-500 border-t pt-6 space-y-1">
            <div className="font-semibold text-gray-700">Scoring logic (summary)</div>
            {Object.entries(data.scoring_notes).map(([k, v]) => (
              <p key={k}>
                <span className="font-medium text-gray-600">{humanizeScoringNoteKey(k)}:</span> {humanizeScoringNoteText(String(v))}
              </p>
            ))}
          </section>
        ) : null}

        {auto?.job_states_sample && Object.keys(auto.job_states_sample).length > 0 ? (
          <section className="text-xs text-gray-500 border-t pt-4">
            <details>
              <summary className="cursor-pointer font-semibold text-gray-700 hover:text-indigo-600">
                Technical: sample job state payload (diagnostics)
              </summary>
              <p className="mt-2 text-gray-500 mb-2">
                Raw keys match scheduler / observability registry ids. Primary admin views use readable names in Automation
                Centre and in summaries above where applicable.
              </p>
              <pre className="max-h-56 overflow-auto rounded border border-slate-200 bg-slate-50 p-3 font-mono text-[11px] text-slate-800 whitespace-pre-wrap">
                {JSON.stringify(auto.job_states_sample, null, 2)}
              </pre>
            </details>
          </section>
        ) : null}
      </div>
    </UnifiedAdminLayout>
  );
}
