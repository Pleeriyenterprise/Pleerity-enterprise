import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Activity, AlertTriangle, CheckCircle, RefreshCw, Clock } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminSystemHealthPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);
    adminAPI
      .getObservabilityHealthSummary()
      .then((res) => setData(res.data))
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load health summary');
        toast.error('Failed to load system health');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const formatTime = (iso) => (iso ? new Date(iso).toLocaleString() : '—');
  const visibilityReasonLabel = (code) => {
    if (!code) return '';
    const map = {
      scheduler_runtime_unavailable: 'Scheduler metadata unavailable in this process',
      job_not_registered_in_scheduler_runtime: 'Job not registered in scheduler runtime',
      next_run_not_exposed_by_scheduler: 'Next run not exposed by scheduler',
      no_run_history_not_yet_due: 'No run history yet (first run still future due)',
      no_run_history_overdue: 'No run history and due window has passed',
    };
    return map[code] || code;
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Activity className="w-7 h-7" />
            System Health
          </h1>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={loading ? 'animate-spin w-4 h-4' : 'w-4 h-4'} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 mb-4">{error}</div>
        )}

        {loading && !data && (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-2 border-indigo-600 border-t-transparent" />
          </div>
        )}

        {data?.delivery_unknown_stale_runs?.length > 0 && (
          <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span>
              {data.delivery_unknown_stale_runs.length} run(s) have <strong>delivery unknown</strong> still unresolved after {data.delivery_unknown_stale_hours ?? 6}h. Check Message logs (Automation Centre) or provider webhooks.
            </span>
          </div>
        )}

        {data?.scheduler_runtime?.available === false && (
          <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm">
            Scheduler runtime metadata is unavailable in this API process. Next-run visibility may be incomplete; rely on `job_runs` history and incidents while scheduler ownership is verified.
          </div>
        )}

        {data && (
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <span className="text-sm font-medium text-gray-500">Status</span>
              {(() => {
                const health = data.overall_health ?? (data.status === 'ok' ? 'healthy' : data.status === 'incident' ? 'incident' : 'degraded');
                if (data.status === 'incident' || health === 'incident') {
                  return (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                      <AlertTriangle className="w-4 h-4" />
                      Incident ({data.open_p0_p1_count} P0/P1 open)
                    </span>
                  );
                }
                if (health === 'failed') {
                  return (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                      <AlertTriangle className="w-4 h-4" />
                      Failed
                    </span>
                  );
                }
                if (health === 'attention_required') {
                  return (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                      <AlertTriangle className="w-4 h-4" />
                      Attention required
                    </span>
                  );
                }
                if (health === 'degraded') {
                  return (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-amber-100 text-amber-800">
                      <AlertTriangle className="w-4 h-4" />
                      Degraded
                    </span>
                  );
                }
                return (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                    <CheckCircle className="w-4 h-4" />
                    Healthy
                  </span>
                );
              })()}
              {data.open_incidents_count > 0 && (
                <Link to="/admin/incidents?status=open" className="text-sm text-indigo-600 hover:underline">
                  View {data.open_incidents_count} open incident(s)
                </Link>
              )}
            </div>

            {data.summary_counts && (data.summary_counts.critical_missed > 0 || data.summary_counts.never_ran > 0 || data.summary_counts.failed_24h > 0 || data.summary_counts.degraded_24h > 0) && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
                <strong>Summary:</strong>{' '}
                {[
                  data.summary_counts.critical_missed > 0 && `${data.summary_counts.critical_missed} critical missed`,
                  data.summary_counts.never_ran > 0 && `${data.summary_counts.never_ran} never ran`,
                  data.summary_counts.failed_24h > 0 && `${data.summary_counts.failed_24h} failed (24h)`,
                  data.summary_counts.degraded_24h > 0 && `${data.summary_counts.degraded_24h} degraded (24h)`,
                ].filter(Boolean).join(', ')}
                {data.summary_counts.open_incidents > 0 && ` · ${data.summary_counts.open_incidents} open incident(s)`}
              </div>
            )}

            {data.last_heartbeat_at != null && (
              <div className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-600">
                <span className="font-medium">Scheduler heartbeat:</span>{' '}
                {formatTime(data.last_heartbeat_at)}
                {data.heartbeat_stale && (
                  <span className="ml-2 text-amber-600 font-medium">(stale — scheduler may be down)</span>
                )}
              </div>
            )}

            {data.alerting_configured === false && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm">
                Admin alerting is not configured. Set <code className="bg-amber-100/80 px-1 rounded">ADMIN_ALERT_EMAILS</code> or <code className="bg-amber-100/80 px-1 rounded">OPS_ALERT_EMAIL</code> so failed or missed automations trigger email alerts.
              </div>
            )}

            {data.last_success && Object.values(data.last_success).every((v) => v == null) && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm">
                No job runs have been recorded. The background scheduler may not be running (e.g. startup failure on deploy). Without it, automations do not run, the SLA watchdog cannot create incidents, and admin alert emails will not be sent. Check server logs and set <code className="bg-amber-100/80 px-1 rounded">ADMIN_ALERT_EMAILS</code> for incident alerts.
              </div>
            )}

            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-1">Last successful run</h2>
              <p className="text-sm text-gray-500 mb-3">
                Daily and hourly jobs show &quot;No run yet&quot; until their first scheduled run after server start (e.g. daily_reminders at 9:00 UTC). See <Link to="/admin/automation" className="text-indigo-600 hover:underline">Automation Control Centre</Link> for next run times.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {data.last_success && Object.entries(data.last_success).map(([jobName, finishedAt]) => {
                  const jobState = data.job_states?.[jobName]?.state;
                  const nextRunReasonCode = data.job_states?.[jobName]?.next_run_reason_code;
                  const lastRunReasonCode = data.job_states?.[jobName]?.last_run_reason_code;
                  const isNotYetDue = jobState === 'not_yet_due_since_startup';
                  const label = finishedAt != null
                    ? formatTime(finishedAt)
                    : isNotYetDue
                      ? 'No run yet (next run scheduled)'
                      : 'No run yet';
                  return (
                    <div key={jobName} className="bg-white border border-gray-200 rounded-lg p-4 flex items-center gap-3">
                      <Clock className="w-5 h-5 text-gray-400" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{jobName}</p>
                        <p className={`text-xs ${finishedAt != null ? 'text-gray-500' : 'text-gray-500 italic'}`}>{label}</p>
                        {!finishedAt && (
                          <p className="text-[11px] text-gray-500 mt-0.5">
                            {visibilityReasonLabel(lastRunReasonCode || nextRunReasonCode)}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {data.recent_failures && data.recent_failures.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-3">Recent failures</h2>
                <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left font-medium text-gray-700">Job</th>
                        <th className="px-4 py-2 text-left font-medium text-gray-700">Time</th>
                        <th className="px-4 py-2 text-left font-medium text-gray-700">Error</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {data.recent_failures.map((row, i) => (
                        <tr key={i}>
                          <td className="px-4 py-2 font-mono text-xs">{row.job_name}</td>
                          <td className="px-4 py-2 text-gray-600">{formatTime(row.finished_at)}</td>
                          <td className="px-4 py-2 text-red-600 truncate max-w-xs" title={row.error_message}>
                            {row.error_message || '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2">
                  <Link to="/admin/automation" className="text-indigo-600 hover:underline text-sm">
                    View Automation Control Centre →
                  </Link>
                </p>
              </div>
            )}

            <p className="text-sm text-gray-500">
              <Link to="/admin/incidents" className="text-indigo-600 hover:underline">Incidents</Link>
              {' · '}
              <Link to="/admin/automation" className="text-indigo-600 hover:underline">Automation Control Centre</Link>
            </p>
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
