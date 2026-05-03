import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Zap, Play, RefreshCw, Clock, CheckCircle, AlertTriangle, XCircle, HelpCircle, FileText, Download } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import {
  formatComplianceScoreSnapshotsOutcomeSummary,
  getComplianceScoreSnapshotsDisplayLastRun,
} from '../utils/complianceScoreSnapshotsAdminSummary';
import {
  formatComplianceRecalcWorkerOutcomeSummary,
  getComplianceRecalcWorkerDisplayLastRun,
} from '../utils/complianceRecalcWorkerAdminSummary';
import {
  formatRiskSignalRegenOutcomeSummary,
  getRiskSignalRegenDisplayLastRun,
} from '../utils/riskSignalRegenWorkerAdminSummary';
import {
  AUTOMATION_CENTRE_MESSAGE_LOGS_JOBS as MESSAGE_LOGS_JOBS,
  getAutomationCentreDegradedReviewTitle,
} from '../utils/automationCentreReviewHints';

const JOB_STATE = {
  healthy: { label: 'Healthy', className: 'bg-green-100 text-green-800', Icon: CheckCircle },
  degraded: { label: 'Degraded', className: 'bg-amber-100 text-amber-800', Icon: AlertTriangle },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-800', Icon: XCircle },
  missed: { label: 'Missed', className: 'bg-orange-100 text-orange-800', Icon: AlertTriangle },
  never_ran: { label: 'Never ran', className: 'bg-gray-100 text-gray-700', Icon: HelpCircle },
  never_ran_and_overdue: { label: 'Never ran (overdue)', className: 'bg-red-50 text-red-800', Icon: AlertTriangle },
  not_yet_due_since_startup: { label: 'Not yet due', className: 'bg-slate-100 text-slate-600', Icon: Clock },
  no_runs: { label: 'No runs', className: 'bg-gray-100 text-gray-600', Icon: HelpCircle },
  not_due: { label: 'Not due', className: 'bg-slate-100 text-slate-700', Icon: Clock },
  conditional_no_output: { label: 'No output (OK)', className: 'bg-slate-100 text-slate-600', Icon: CheckCircle },
};

const DIAGNOSTIC_REASON = {
  registered_not_yet_due: 'Registered and awaiting first scheduled run.',
  registered_overdue_never_ran: 'Registered but overdue with no run history.',
  startup_reconciliation_issue: 'Not yet reconciled by startup recovery scope.',
  triggered_but_uninstrumented: 'Manual trigger exists but no instrumented run recorded.',
  conditionally_no_output: 'Job ran successfully with no qualifying records.',
  UI_state_bug: 'Run history exists but job visibility mapping is inconsistent.',
  database_environment_mismatch: 'Run history exists but scheduler registration missing in this process.',
  'database/environment_mismatch': 'Run history exists but scheduler registration missing in this process.',
};

const VISIBILITY_REASON = {
  scheduler_runtime_unavailable: 'Scheduler runtime metadata unavailable in this process.',
  not_registered_in_scheduler_runtime: 'Job is not currently registered in in-process scheduler runtime.',
  job_not_registered_in_scheduler_runtime: 'Job is not currently registered in in-process scheduler runtime.',
  next_run_not_exposed_by_scheduler: 'Scheduler did not expose next run time for this job.',
  no_run_history_not_yet_due: 'No run history yet because first scheduled run is still in the future.',
  no_run_history_overdue: 'No run history and first due window has passed.',
};

function getJobState(info, jobName, heartbeatStale, nextRunIso) {
  if (jobName === 'scheduler_heartbeat' && heartbeatStale) return 'failed';
  const last = info?.lastRun;
  if (!last) {
    // No runs yet: if next run is in the future, job is "not yet due"; otherwise overdue
    if (nextRunIso) {
      const nextRunTime = new Date(nextRunIso).getTime();
      const now = Date.now();
      if (nextRunTime > now + 60 * 1000) return 'not_yet_due_since_startup'; // 60s tolerance
    }
    return 'never_ran_and_overdue';
  }
  const status = last.status || '';
  if (status === 'success') return 'healthy';
  if (status === 'degraded') return 'degraded';
  if (status === 'failed') return 'failed';
  const nextRun = info?.nextRun;
  if (nextRun && new Date(nextRun) < new Date() && !last) return 'missed';
  return 'never_ran_and_overdue';
}

export default function AdminAutomationCentrePage() {
  const [jobRuns, setJobRuns] = useState({ items: [], total: 0 });
  const [frameworkAudit, setFrameworkAudit] = useState(null);
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
      adminAPI.getAutomationFrameworkAudit(),
      adminAPI.getObservabilityHealthSummary().catch(() => ({ data: null })),
    ])
      .then(([runsRes, auditRes, healthRes]) => {
        setJobRuns(runsRes.data);
        setFrameworkAudit(auditRes?.data || null);
        setHealthSummary(healthRes?.data || null);
      })
      .catch(() => toast.error('Failed to load automation data'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const [runNowConfirm, setRunNowConfirm] = useState(null);
  const [cardFilter, setCardFilter] = useState(null);

  const handleRunNowClick = (jobId) => {
    setRunNowConfirm(jobId);
  };

  const handleRunNowConfirm = () => {
    if (!runNowConfirm) return;
    const jobId = runNowConfirm;
    setRunNowConfirm(null);
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

  const failed24hByJob = (healthSummary?.failed_runs_24h_by_job || []).reduce((acc, row) => {
    if (row?.job_name) acc[row.job_name] = row.count || 0;
    return acc;
  }, {});
  const degraded24hByJob = (healthSummary?.degraded_runs_24h_by_job || []).reduce((acc, row) => {
    if (row?.job_name) acc[row.job_name] = row.count || 0;
    return acc;
  }, {});

  const byJobRuns = (jobRuns.items || []).reduce((acc, r) => {
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
  const byJobInventory = (frameworkAudit?.inventory || []).reduce((acc, item) => {
    acc[item.job_name] = item;
    return acc;
  }, {});

  const formatTime = (iso) => (iso ? new Date(iso).toLocaleString() : '—');
  const inventory = frameworkAudit?.inventory || [];

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
  const jobIds = [...new Set([
    ...Object.keys(byJobRuns),
    ...inventory.map((i) => i.job_name),
    ...Object.keys(failed24hByJob),
    ...Object.keys(degraded24hByJob),
  ].filter(Boolean))].sort();
  const deliveryUnknownJobNames = new Set(
    (healthSummary?.delivery_unknown_stale_runs || []).map((r) => r.job_name).filter(Boolean)
  );
  const filteredJobIds = (() => {
    if (!cardFilter) return jobIds;
    if (cardFilter === 'delivery_unknown_stale') return jobIds.filter((jid) => deliveryUnknownJobNames.has(jid));
    if (cardFilter === 'heartbeat_stale') return jobIds.filter((jid) => jid === 'scheduler_heartbeat');
    if (cardFilter === 'open_incidents') return jobIds; // "Open incidents" links away; no table filter
    // Summary cards count *run rows* in 24h; job_states reflect latest outcome per registry job — align filters.
    if (cardFilter === 'failed') {
      return jobIds.filter(
        (jid) => (failed24hByJob[jid] || 0) > 0 || healthSummary?.job_states?.[jid]?.state === 'failed',
      );
    }
    if (cardFilter === 'degraded') {
      return jobIds.filter(
        (jid) => (degraded24hByJob[jid] || 0) > 0 || healthSummary?.job_states?.[jid]?.state === 'degraded',
      );
    }
    return jobIds.filter((jid) => healthSummary?.job_states?.[jid]?.state === cardFilter);
  })();
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

        {(healthSummary?.delivery_unknown_stale_runs?.length > 0) && (
          <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span>
              {healthSummary.delivery_unknown_stale_runs.length} run(s) still have <strong>delivery unknown</strong> unresolved after {healthSummary.delivery_unknown_stale_hours ?? 6}h. Check Message logs or provider webhooks for those jobs.
            </span>
          </div>
        )}

        {healthSummary?.grace_period_explanation && (
          <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700">
            {healthSummary.grace_period_explanation}
          </div>
        )}
        {healthSummary?.summary_counts && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 mb-4">
            {healthSummary.summary_counts.critical_missed > 0 && (
              <button
                type="button"
                onClick={() => setCardFilter(cardFilter === 'missed' ? null : 'missed')}
                className={`rounded-lg border px-3 py-2 text-sm text-left transition-colors ${cardFilter === 'missed' ? 'ring-2 ring-orange-400 border-orange-300 bg-orange-100' : 'border-orange-200 bg-orange-50 hover:bg-orange-100'}`}
              >
                <span className="font-medium text-orange-800">{healthSummary.summary_counts.critical_missed}</span>
                <span className="text-orange-700"> critical job(s) missed</span>
              </button>
            )}
            {(healthSummary.summary_counts.never_ran > 0 || healthSummary.summary_counts.never_ran_overdue > 0) && (
              <button
                type="button"
                onClick={() => setCardFilter(cardFilter === 'never_ran_and_overdue' ? null : 'never_ran_and_overdue')}
                className={`rounded-lg border px-3 py-2 text-sm text-left transition-colors ${cardFilter === 'never_ran_and_overdue' ? 'ring-2 ring-red-400 border-red-300 bg-red-50' : 'border-gray-300 bg-gray-50 hover:bg-gray-100'}`}
              >
                <span className="font-medium text-gray-800">{healthSummary.summary_counts.never_ran ?? healthSummary.summary_counts.never_ran_overdue ?? 0}</span>
                <span className="text-gray-600"> critical job(s) never ran</span>
              </button>
            )}
            {healthSummary.summary_counts.not_yet_due_since_startup > 0 && (
              <button
                type="button"
                onClick={() => setCardFilter(cardFilter === 'not_yet_due_since_startup' ? null : 'not_yet_due_since_startup')}
                className={`rounded-lg border px-3 py-2 text-sm text-left transition-colors ${cardFilter === 'not_yet_due_since_startup' ? 'ring-2 ring-slate-400 border-slate-300 bg-slate-100' : 'border-slate-200 bg-slate-50 hover:bg-slate-100'}`}
              >
                <span className="font-medium text-slate-700">{healthSummary.summary_counts.not_yet_due_since_startup}</span>
                <span className="text-slate-600"> not yet due</span>
              </button>
            )}
            {healthSummary.summary_counts.degraded_24h > 0 && (
              <button
                type="button"
                onClick={() => setCardFilter(cardFilter === 'degraded' ? null : 'degraded')}
                title="Count = degraded job_runs in the last 24h. Table lists job names with ≥1 degraded run or current degraded state."
                className={`rounded-lg border px-3 py-2 text-sm text-left transition-colors ${cardFilter === 'degraded' ? 'ring-2 ring-amber-400 border-amber-300 bg-amber-100' : 'border-amber-200 bg-amber-50 hover:bg-amber-100'}`}
              >
                <span className="font-medium text-amber-800">{healthSummary.summary_counts.degraded_24h}</span>
                <span className="text-amber-700"> degraded runs (24h)</span>
              </button>
            )}
            {healthSummary.summary_counts.failed_24h > 0 && (
              <button
                type="button"
                onClick={() => setCardFilter(cardFilter === 'failed' ? null : 'failed')}
                title="Count = failed job_runs in the last 24h (same job may appear more than once). Table lists distinct job names with at least one failure."
                className={`rounded-lg border px-3 py-2 text-sm text-left transition-colors ${cardFilter === 'failed' ? 'ring-2 ring-red-400 border-red-300 bg-red-100' : 'border-red-200 bg-red-50 hover:bg-red-100'}`}
              >
                <span className="font-medium text-red-800">{healthSummary.summary_counts.failed_24h}</span>
                <span className="text-red-700"> failed runs (24h)</span>
              </button>
            )}
            {healthSummary.summary_counts.open_incidents > 0 && (
              <Link
                to="/admin/incidents"
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-left transition-colors hover:bg-red-100 hover:border-red-300 inline-block"
              >
                <span className="font-medium text-red-800">{healthSummary.summary_counts.open_incidents}</span>
                <span className="text-red-700"> open incidents</span>
              </Link>
            )}
            {healthSummary.summary_counts.heartbeat_stale > 0 && (
              <button
                type="button"
                onClick={() => setCardFilter(cardFilter === 'heartbeat_stale' ? null : 'heartbeat_stale')}
                className={`rounded-lg border px-3 py-2 text-sm text-left transition-colors ${cardFilter === 'heartbeat_stale' ? 'ring-2 ring-red-400 border-red-300 bg-red-100' : 'border-red-200 bg-red-50 hover:bg-red-100'}`}
              >
                <span className="font-medium text-red-800">Stale</span>
                <span className="text-red-700"> heartbeat</span>
              </button>
            )}
            {healthSummary.summary_counts.delivery_unknown_stale > 0 && (
              <button
                type="button"
                onClick={() => setCardFilter(cardFilter === 'delivery_unknown_stale' ? null : 'delivery_unknown_stale')}
                className={`rounded-lg border px-3 py-2 text-sm text-left transition-colors ${cardFilter === 'delivery_unknown_stale' ? 'ring-2 ring-amber-400 border-amber-300 bg-amber-100' : 'border-amber-200 bg-amber-50 hover:bg-amber-100'}`}
              >
                <span className="font-medium text-amber-800">{healthSummary.summary_counts.delivery_unknown_stale}</span>
                <span className="text-amber-700"> delivery unknown stale</span>
              </button>
            )}
          </div>
        )}
        {cardFilter && cardFilter !== 'open_incidents' && (
          <p className="mb-2 text-sm text-gray-600">
            Showing only: <strong>{
              cardFilter === 'missed' ? 'Critical missed'
              : cardFilter === 'never_ran_and_overdue' ? 'Never ran (overdue)'
              : cardFilter === 'not_yet_due_since_startup' ? 'Not yet due'
              : cardFilter === 'degraded' ? 'Degraded runs (24h)'
              : cardFilter === 'failed' ? 'Failed runs (24h)'
              : cardFilter === 'heartbeat_stale' ? 'Stale heartbeat'
              : cardFilter === 'delivery_unknown_stale' ? 'Delivery unknown stale'
              : cardFilter
            }</strong>
            {' '}<button type="button" onClick={() => setCardFilter(null)} className="text-indigo-600 hover:underline">Clear filter</button>
          </p>
        )}

        <p className="mb-3 text-sm text-gray-600">
          Routine automation should run automatically. Use manual run only for <strong>recovery or testing</strong>. Degraded = some sends failed or skipped; review outcome counts and Message logs when available.
        </p>

        {hasNoRuns && (
          <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm">
            No job runs have been recorded yet. If the background scheduler did not start (e.g. check deployment logs), jobs will not run and the SLA watchdog will not create incidents or send admin alerts. Ensure the API process runs with the scheduler enabled and set <code className="bg-amber-100/80 px-1 rounded">ADMIN_ALERT_EMAILS</code> for incident email alerts.
          </div>
        )}

        <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm" style={{ minWidth: 'max(100%, 56rem)' }}>
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Job</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Status</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Last run</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Last success</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Last degraded</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Failures (24h)</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Next schedule</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Reason</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Recommended action</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredJobIds.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-6 text-center text-gray-500">
                    {jobIds.length === 0
                      ? 'No scheduled jobs loaded. The background scheduler may not be running—check server startup logs.'
                      : `No jobs match the filter "${cardFilter}". Clear filter to see all.`}
                  </td>
                </tr>
              ) : (
                filteredJobIds.map((jobName) => {
                  const runInfo = byJobRuns[jobName] || { lastRun: null, lastSuccess: null, lastDegraded: null, lastFailed: null, failures24h: 0, degraded24h: 0 };
                  const invInfo = byJobInventory[jobName] || null;
                  const lastRunFromInventory = invInfo?.last_run_id
                    ? {
                        id: invInfo.last_run_id,
                        job_name: jobName,
                        status: invInfo.last_status,
                        finished_at: invInfo.last_finished_at,
                        created_at: invInfo.last_started_at,
                      }
                    : null;
                  const info = {
                    ...runInfo,
                    lastRun: runInfo.lastRun || lastRunFromInventory,
                  };
                  const backendState = healthSummary?.job_states?.[jobName];
                  const state = backendState?.state || getJobState(info, jobName, heartbeatStale, invInfo?.next_run_time);
                  const lastRunTs = info.lastRun?.finished_at || info.lastRun?.created_at || backendState?.last_run;
                  const lastSuccessTs = info.lastSuccess?.finished_at || backendState?.last_success;
                  const lastDegradedTs = info.lastDegraded?.finished_at || backendState?.last_degraded;
                  const failures24hCount = Math.max(failed24hByJob[jobName] || 0, info.failures24h || 0);
                  const degraded24hCount = Math.max(degraded24hByJob[jobName] || 0, info.degraded24h || 0);
                  let reason =
                    backendState?.reason ||
                    VISIBILITY_REASON[invInfo?.next_run_reason] ||
                    VISIBILITY_REASON[invInfo?.last_run_reason] ||
                    DIAGNOSTIC_REASON[invInfo?.diagnostic_category] ||
                    '';
                  if (backendState?.last_failure_message && (state === 'failed' || failures24hCount > 0)) {
                    reason = reason ? `${reason} — ${backendState.last_failure_message}` : backendState.last_failure_message;
                  }
                  if (!reason && info.lastFailed?.error_message && failures24hCount > 0) {
                    reason = info.lastFailed.error_message;
                  }
                  const recommendedAction =
                    backendState?.recommended_action ||
                    (!invInfo?.can_be_run_manually && invInfo ? 'Manual run intentionally excluded for this job contract.' : '');
                  const stateConfig = JOB_STATE[state] || JOB_STATE.no_runs;
                  const StateIcon = stateConfig.Icon;
                  const riskRegenLast =
                    jobName === 'risk_signal_regen_worker'
                      ? getRiskSignalRegenDisplayLastRun(runInfo, invInfo)
                      : null;
                  const riskRegenBundle =
                    jobName === 'risk_signal_regen_worker'
                      ? formatRiskSignalRegenOutcomeSummary(riskRegenLast)
                      : null;
                  const snapshotLast =
                    jobName === 'compliance_score_snapshots'
                      ? getComplianceScoreSnapshotsDisplayLastRun(runInfo, invInfo)
                      : null;
                  const snapshotBundle =
                    jobName === 'compliance_score_snapshots'
                      ? formatComplianceScoreSnapshotsOutcomeSummary(snapshotLast)
                      : null;
                  const recalcLast =
                    jobName === 'compliance_recalc_worker'
                      ? getComplianceRecalcWorkerDisplayLastRun(runInfo, invInfo)
                      : null;
                  const recalcBundle =
                    jobName === 'compliance_recalc_worker'
                      ? formatComplianceRecalcWorkerOutcomeSummary(recalcLast)
                      : null;
                  return (
                    <tr key={jobName}>
                      <td className="px-4 py-2 font-mono text-xs align-top">
                        <div>{jobName}</div>
                        {jobName === 'risk_signal_regen_worker' && riskRegenBundle && (
                          <div
                            className="mt-1.5 space-y-0.5 text-[11px] text-gray-600 font-sans max-w-md"
                            data-testid="risk-regen-outcome-summary"
                          >
                            {riskRegenBundle.headlineLines.map((t, i) => (
                              <div key={i}>{t}</div>
                            ))}
                            {riskRegenBundle.showTechnicalDetail &&
                              riskRegenBundle.technicalPayload &&
                              Object.keys(riskRegenBundle.technicalPayload).length > 0 && (
                                <details className="mt-1 text-gray-500 font-sans">
                                  <summary className="cursor-pointer hover:underline select-none">
                                    Technical details
                                  </summary>
                                  <pre className="mt-1 whitespace-pre-wrap break-all text-[10px] bg-gray-50 p-1.5 rounded border border-gray-100 max-h-40 overflow-auto">
                                    {JSON.stringify(riskRegenBundle.technicalPayload, null, 2)}
                                  </pre>
                                </details>
                              )}
                          </div>
                        )}
                        {jobName === 'compliance_score_snapshots' && snapshotBundle && (
                          <div
                            className="mt-1.5 space-y-0.5 text-[11px] text-gray-600 font-sans max-w-md"
                            data-testid="compliance-score-snapshots-outcome-summary"
                          >
                            {snapshotBundle.headlineLines.map((t, i) => (
                              <div key={`snap-${i}`}>{t}</div>
                            ))}
                            {snapshotBundle.showTechnicalDetail &&
                              snapshotBundle.technicalPayload &&
                              Object.keys(snapshotBundle.technicalPayload).length > 0 && (
                                <details className="mt-1 text-gray-500 font-sans">
                                  <summary className="cursor-pointer hover:underline select-none">
                                    Technical details
                                  </summary>
                                  <pre className="mt-1 whitespace-pre-wrap break-all text-[10px] bg-gray-50 p-1.5 rounded border border-gray-100 max-h-40 overflow-auto">
                                    {JSON.stringify(snapshotBundle.technicalPayload, null, 2)}
                                  </pre>
                                </details>
                              )}
                          </div>
                        )}
                        {jobName === 'compliance_recalc_worker' && recalcBundle && (
                          <div
                            className="mt-1.5 space-y-0.5 text-[11px] text-gray-600 font-sans max-w-md"
                            data-testid="compliance-recalc-worker-outcome-summary"
                          >
                            {recalcBundle.headlineLines.map((t, i) => (
                              <div key={`recalc-${i}`}>{t}</div>
                            ))}
                            {recalcBundle.showTechnicalDetail &&
                              recalcBundle.technicalPayload &&
                              Object.keys(recalcBundle.technicalPayload).length > 0 && (
                                <details className="mt-1 text-gray-500 font-sans">
                                  <summary className="cursor-pointer hover:underline select-none">
                                    Technical details
                                  </summary>
                                  <pre className="mt-1 whitespace-pre-wrap break-all text-[10px] bg-gray-50 p-1.5 rounded border border-gray-100 max-h-40 overflow-auto">
                                    {JSON.stringify(recalcBundle.technicalPayload, null, 2)}
                                  </pre>
                                </details>
                              )}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${stateConfig.className}`}>
                          <StateIcon className="w-3.5 h-3.5" />
                          {stateConfig.label}
                        </span>
                        {degraded24hCount > 0 && state !== 'degraded' && (
                          <span className="ml-1 text-amber-600 text-xs">({degraded24hCount} degraded run{degraded24hCount !== 1 ? 's' : ''} 24h)</span>
                        )}
                        {failures24hCount > 0 && state !== 'failed' && (
                          <span className="ml-1 text-red-600 text-xs" title="Failed run events in last 24h (latest run may be success)">({failures24hCount} failed 24h)</span>
                        )}
                        {(state === 'degraded' || state === 'failed') && (
                          <span
                            className="ml-1.5 text-gray-500 text-xs"
                            title={getAutomationCentreDegradedReviewTitle(jobName)}
                          >
                            (review)
                          </span>
                        )}
                        {state === 'degraded' && healthSummary?.delivery_unknown_stale_runs?.some((r) => r.job_name === jobName) && (
                          <span className="ml-1 text-amber-600 text-xs" title="Delivery unknown still high after run; check webhooks or Message logs.">
                            (unknown stale)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-gray-600">{formatTime(lastRunTs)}</td>
                      <td className="px-4 py-2 text-gray-600">{formatTime(lastSuccessTs)}</td>
                      <td className="px-4 py-2 text-amber-600">{formatTime(lastDegradedTs)}</td>
                      <td className="px-4 py-2">{failures24hCount > 0 ? <span className="text-red-600">{failures24hCount}</span> : '—'}</td>
                      <td className="px-4 py-2 text-gray-600">{invInfo?.next_run_time ? formatTime(invInfo.next_run_time) : '—'}</td>
                      <td className="px-4 py-2 text-gray-500 text-xs max-w-[14rem]" title={reason}>{reason || invInfo?.diagnostic_category || '—'}</td>
                      <td className="px-4 py-2 text-gray-600 text-xs max-w-[14rem]" title={recommendedAction}>{recommendedAction || '—'}</td>
                      <td className="px-4 py-2">
                        <div className="flex flex-wrap items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleRunNowClick(jobName)}
                            disabled={running === jobName}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-gray-400 rounded bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                            title="Use only for recovery or testing"
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

        {runNowConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-labelledby="run-now-confirm-title">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full m-4 p-4">
              <h2 id="run-now-confirm-title" className="text-lg font-semibold text-gray-900 mb-2">Run job now?</h2>
              <p className="text-sm text-gray-600 mb-4">
                Routine automation should run automatically. Use manual run only for <strong>recovery or testing</strong>. Running this job now will execute it once.
              </p>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setRunNowConfirm(null)} className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
                <button type="button" onClick={handleRunNowConfirm} className="px-3 py-1.5 text-sm bg-electric-teal text-white rounded hover:opacity-90">Run now</button>
              </div>
            </div>
          </div>
        )}

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
