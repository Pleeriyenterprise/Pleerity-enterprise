import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Zap, Play, RefreshCw, Clock } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminAutomationCentrePage() {
  const [jobRuns, setJobRuns] = useState({ items: [], total: 0 });
  const [jobsStatus, setJobsStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([adminAPI.getJobRuns({ limit: 200 }), adminAPI.getJobsStatus()])
      .then(([runsRes, statusRes]) => {
        setJobRuns(runsRes.data);
        setJobsStatus(statusRes.data);
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
    if (!acc[name]) acc[name] = { lastRun: null, lastSuccess: null, failures24h: 0 };
    if (!acc[name].lastRun || (r.created_at && r.created_at > (acc[name].lastRun?.created_at || '')))
      acc[name].lastRun = r;
    if (r.status === 'success' && (!acc[name].lastSuccess || (r.finished_at > (acc[name].lastSuccess?.finished_at || ''))))
      acc[name].lastSuccess = r;
    if (r.status === 'failed') {
      const t = r.finished_at || r.created_at;
      if (t && new Date(t) > new Date(Date.now() - 24 * 60 * 60 * 1000)) acc[name].failures24h += 1;
    }
    return acc;
  }, {});

  const formatTime = (iso) => (iso ? new Date(iso).toLocaleString() : '—');
  const nextRuns = jobsStatus?.scheduled_jobs || [];

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

        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Job</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Last run</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Last success</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Failures (24h)</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Next schedule</th>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {Object.entries(byJob).map(([jobName, info]) => {
                const next = nextRuns.find((j) => j.id === jobName);
                return (
                  <tr key={jobName}>
                    <td className="px-4 py-2 font-mono text-xs">{jobName}</td>
                    <td className="px-4 py-2 text-gray-600">{formatTime(info.lastRun?.finished_at || info.lastRun?.created_at)}</td>
                    <td className="px-4 py-2 text-gray-600">{formatTime(info.lastSuccess?.finished_at)}</td>
                    <td className="px-4 py-2">{info.failures24h > 0 ? <span className="text-red-600">{info.failures24h}</span> : '—'}</td>
                    <td className="px-4 py-2 text-gray-600">{next?.next_run ? formatTime(next.next_run) : '—'}</td>
                    <td className="px-4 py-2">
                      <button
                        type="button"
                        onClick={() => handleRunNow(jobName)}
                        disabled={running === jobName}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
                      >
                        {running === jobName ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                        Run now
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <p className="mt-4 text-sm text-gray-500">
          <Link to="/admin/system-health" className="text-indigo-600 hover:underline">System Health</Link>
          {' · '}
          <Link to="/admin/incidents" className="text-indigo-600 hover:underline">Incidents</Link>
        </p>
      </div>
    </UnifiedAdminLayout>
  );
}
