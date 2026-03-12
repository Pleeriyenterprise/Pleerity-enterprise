import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Zap, Play, RefreshCw, Clock, CheckCircle, AlertTriangle, XCircle, HelpCircle, FileText, Download } from 'lucide-react';
import { toast } from 'sonner';

// Jobs that have message_logs drill-down (delivery reconciliation)
const MESSAGE_LOGS_JOBS = new Set([
  'daily_reminders',
  'monthly_digest',
  'pending_verification_digest',
  'compliance_check_morning',
  'compliance_check_evening',
  'scheduled_reports',
]);

const JOB_STATE = {
  healthy: { label: 'Healthy', className: 'bg-green-100 text-green-800', Icon: CheckCircle },
  degraded: { label: 'Degraded', className: 'bg-amber-100 text-amber-800', Icon: AlertTriangle },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-800', Icon: XCircle },
  missed: { label: 'Missed', className: 'bg-orange-100 text-orange-800', Icon: AlertTriangle },
  no_runs: { label: 'No runs', className: 'bg-gray-100 text-gray-600', Icon: HelpCircle },
};

function getJobState(info, jobName, heartbeatStale) {
  if (jobName === 'scheduler_heartbeat' && heartbeatStale) return 'failed';
  const last = info?.lastRun;
  if (!last) return 'no_runs';
  const status = last.status || '';
  if (status === 'success') return 'healthy';
  if (status === 'degraded') return 'degraded';
  if (status === 'failed') return 'failed';
  const nextRun = info?.nextRun;
  if (nextRun && new Date(nextRun) < new Date() && !last) return 'missed';
  return 'no_runs';
}

export default function AdminAutomationCentrePage() {
  const [jobRuns, setJobRuns] = useState({ items: [], total: 0 });
  const [jobsStatus, setJobsStatus] = useState(null);
  const [healthSummary, setHealthSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(null);
  const [messageLogsRun, setMessageLogsRun] = useState(null);
  const [messageLogs, setMessageLogs] = useState({ items: [], job_name: '' });
  const [messageLogsLoading, setMessageLogsLoading] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([
      adminAPI.getJobRuns({ limit: 200 }),
      adminAPI.getJobsStatus(),
      adminAPI.getObservabilityHealthSummary().catch(() => ({ data: null })),
    ])
      .then(([runsRes, statusRes, healthRes]) => {
        setJobRuns(runsRes.data);
        setJobsStatus(statusRes.data);
        setHealthSummary(healthRes?.data || null);
      })
      .catch(() => toast.error('Failed to load automation data'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleRunNow = (jobId) => {
    setRunning(jobId);
    adminAPI
      .runJobNow(jobId)
      .then((res) => {
        toast.success(res.data?.message || `Job ${jobId} completed`);
        load();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || `Failed to run ${jobId}`))
      .finally(() => setRunning(null));
  };

  const byJob = (jobRuns.items || []).reduce((acc, r) => {
    const name = r.job_name || 'unknown';
    if (!acc[name]) acc[name] = { lastRun: null, lastSuccess: null, lastDegraded: null, lastFailed: null, failures24h: 0, degraded24h: 0 };
    if (!acc[name].lastRun || (r.finished_at && r.finished_at > (acc[name].lastRun?.finished_at || '')))
      acc[name].lastRun = r;
    if (r.status === 'success' && (!acc[name].lastSuccess || (r.finished_at > (acc[name].lastSuccess?.finished_at || ''))))
      acc[name].lastSuccess = r;
    if (r.status === 'degraded' && (!acc[name].lastDegraded || (r.finished_at > (acc[name].lastDegraded?.finished_at || ''))))
      acc[name].lastDegraded = r;
    if (r.status === 'failed' && (!acc[name].lastFailed || (r.finished_at > (acc[name].lastFailed?.finished_at || ''))))
      acc[name].lastFailed = r;
    if (r.status === 'failed') {
      const t = r.finished_at || r.created_at;
      if (t && new Date(t) > new Date(Date.now() - 24 * 60 * 60 * 1000)) acc[name].failures24h += 1;
    }
    if (r.status === 'degraded') {
      const t = r.finished_at || r.created_at;
      if (t && new Date(t) > new Date(Date.now() - 24 * 60 * 60 * 1000)) acc[name].degraded24h += 1;
    }
    return acc;
  }, {});

  const formatTime = (iso) => (iso ? new Date(iso).toLocaleString() : '—');
  const nextRuns = jobsStatus?.scheduled_jobs || [];

  const openMessageLogs = (run) => {
    if (!run?.id) return;
    setMessageLogsRun(run);
    setMessageLogs({ items: [], job_name: run.job_name || '' });
    setMessageLogsLoading(true);
    adminAPI
      .getJobRunMessageLogs(run.id, { format: 'json', limit: 500 })
      .then((res) => setMessageLogs({ items: res.data?.items || [], job_name: res.data?.job_name || run.job_name || '' }))
      .catch(() => toast.error('Failed to load message logs'))
      .finally(() => setMessageLogsLoading(false));
  };
  const closeMessageLogs = () => {
    setMessageLogsRun(null);
    setMessageLogs({ items: [], job_name: '' });
  };
  const exportMessageLogsCsv = () => {
    if (!messageLogsRun?.id) return;
    adminAPI
      .getJobRunMessageLogsCsv(messageLogsRun.id)
      .then((res) => {
        const blob = res.data instanceof Blob ? res.data : new Blob([res.data], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `message_logs_run_${messageLogsRun.id}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success('CSV downloaded');
      })
      .catch(() => toast.error('Failed to export CSV'));
  };
  const heartbeatStale = healthSummary?.heartbeat_stale === true;
  // Show all scheduled jobs even when there are no runs (so table is never empty if scheduler is up)
  const jobIds = [...new Set([...Object.keys(byJob), ...nextRuns.map((j) => j.id)].filter(Boolean))].sort();
  const hasNoRuns = !jobRuns.items?.length && jobIds.length > 0;

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Zap className="w-7 h-7" />
            Automation Control Centre
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

        {loading && !jobRuns.items?.length && (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-2 border-indigo-600 border-t-transparent" />
          </div>
        )}

        {heartbeatStale && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-800 px-4 py-3 text-sm flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            Scheduler heartbeat is stale. The background scheduler may have stopped—jobs are not running. Check server logs and restart the API process.
          </div>
        )}

        {hasNoRuns && (
          <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm">
            No job runs have been recorded yet. If the background scheduler did not start (e.g. check deployment logs), jobs will not run and the SLA watchdog will not create incidents or send admin alerts. Ensure the API process runs with the scheduler enabled and set <code className="bg-amber-100/80 px-1 rounded">ADMIN_ALERT_EMAILS</code> for incident email alerts.
          </div>
        )}

        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Job</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Status</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Last run</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Last success</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Last degraded</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Failures (24h)</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Next schedule</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {jobIds.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-gray-500">
                    No scheduled jobs loaded. The background scheduler may not be running—check server startup logs.
                  </td>
                </tr>
              ) : (
                jobIds.map((jobName) => {
                  const info = byJob[jobName] || { lastRun: null, lastSuccess: null, lastDegraded: null, lastFailed: null, failures24h: 0, degraded24h: 0 };
                  const next = nextRuns.find((j) => j.id === jobName);
                  const state = getJobState(info, jobName, heartbeatStale);
                  const stateConfig = JOB_STATE[state] || JOB_STATE.no_runs;
                  const StateIcon = stateConfig.Icon;
                  return (
                    <tr key={jobName}>
                      <td className="px-4 py-2 font-mono text-xs">{jobName}</td>
                      <td className="px-4 py-2">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${stateConfig.className}`}>
                          <StateIcon className="w-3.5 h-3.5" />
                          {stateConfig.label}
                        </span>
                        {info.degraded24h > 0 && state !== 'degraded' && (
                          <span className="ml-1 text-amber-600 text-xs">({info.degraded24h} degraded 24h)</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-gray-600">{formatTime(info.lastRun?.finished_at || info.lastRun?.created_at)}</td>
                      <td className="px-4 py-2 text-gray-600">{formatTime(info.lastSuccess?.finished_at)}</td>
                      <td className="px-4 py-2 text-amber-600">{formatTime(info.lastDegraded?.finished_at)}</td>
                      <td className="px-4 py-2">{info.failures24h > 0 ? <span className="text-red-600">{info.failures24h}</span> : '—'}</td>
                      <td className="px-4 py-2 text-gray-600">{next?.next_run ? formatTime(next.next_run) : '—'}</td>
                      <td className="px-4 py-2">
                        <div className="flex flex-wrap items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleRunNow(jobName)}
                            disabled={running === jobName}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
                          >
                            {running === jobName ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                            Run now
                          </button>
                          {MESSAGE_LOGS_JOBS.has(jobName) && info.lastRun?.id && (state === 'degraded' || state === 'failed') && (
                            <button
                              type="button"
                              onClick={() => openMessageLogs(info.lastRun)}
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-amber-300 rounded hover:bg-amber-50 text-amber-800"
                            >
                              <FileText className="w-3 h-3" />
                              Message logs
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <p className="mt-4 text-sm text-gray-500">
          <Link to="/admin/system-health" className="text-indigo-600 hover:underline">System Health</Link>
          {' · '}
          <Link to="/admin/incidents" className="text-indigo-600 hover:underline">Incidents</Link>
        </p>

        {messageLogsRun && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-labelledby="message-logs-title">
            <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[85vh] flex flex-col m-4">
              <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                <h2 id="message-logs-title" className="text-lg font-semibold text-gray-900">
                  Message logs — {messageLogs.job_name} (run {messageLogsRun.id?.slice(-8)})
                </h2>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={exportMessageLogsCsv}
                    className="inline-flex items-center gap-1 px-2 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
                  >
                    <Download className="w-4 h-4" />
                    Export CSV
                  </button>
                  <button
                    type="button"
                    onClick={closeMessageLogs}
                    className="px-2 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
                  >
                    Close
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-auto p-4">
                {messageLogsLoading ? (
                  <div className="flex justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent" />
                  </div>
                ) : messageLogs.items.length === 0 ? (
                  <p className="text-gray-500 text-sm">No message logs found for this run.</p>
                ) : (
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-2 py-1.5 text-left font-medium text-gray-700">Status</th>
                        <th className="px-2 py-1.5 text-left font-medium text-gray-700">Template</th>
                        <th className="px-2 py-1.5 text-left font-medium text-gray-700">Channel</th>
                        <th className="px-2 py-1.5 text-left font-medium text-gray-700">Recipient</th>
                        <th className="px-2 py-1.5 text-left font-medium text-gray-700">Created</th>
                        <th className="px-2 py-1.5 text-left font-medium text-gray-700">Error</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {messageLogs.items.map((log, i) => (
                        <tr key={i}>
                          <td className="px-2 py-1.5 font-mono text-xs">{log.status ?? '—'}</td>
                          <td className="px-2 py-1.5 font-mono text-xs">{log.template_key ?? '—'}</td>
                          <td className="px-2 py-1.5">{log.channel ?? '—'}</td>
                          <td className="px-2 py-1.5 truncate max-w-[12rem]" title={log.recipient}>{log.recipient ?? '—'}</td>
                          <td className="px-2 py-1.5 text-gray-600">{log.created_at ?? '—'}</td>
                          <td className="px-2 py-1.5 text-red-600 text-xs max-w-[14rem] truncate" title={log.error_message}>{log.error_message ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
