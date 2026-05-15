import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { AlertTriangle, RefreshCw, CheckCircle, MessageSquare } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

const VALID_STATUS = ['open', 'acknowledged', 'resolved'];

export default function AdminIncidentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFromUrl = searchParams.get('status');
  const initialStatus = statusFromUrl && VALID_STATUS.includes(statusFromUrl) ? statusFromUrl : 'open';
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [lifecycleFilter, setLifecycleFilter] = useState('');
  const [opsFilter, setOpsFilter] = useState('');
  const [ackNote, setAckNote] = useState({});
  const [resolveNote, setResolveNote] = useState({});

  const setStatus = (value) => {
    setStatusFilter(value);
    setSearchParams(value === 'open' ? {} : { status: value }, { replace: true });
  };

  // Sync filter from URL when navigating (e.g. link to ?status=open)
  useEffect(() => {
    const s = searchParams.get('status');
    if (s && VALID_STATUS.includes(s) && s !== statusFilter) setStatusFilter(s);
  }, [searchParams, statusFilter]);

  const load = useCallback(() => {
    setLoading(true);
    const params = { status: statusFilter, limit: 50 };
    if (lifecycleFilter) params.lifecycle_state = lifecycleFilter;
    if (opsFilter === 'deployment') params.deployment_related = true;
    if (opsFilter === 'flapping') params.flapping = true;
    adminAPI
      .getIncidents(params)
      .then((res) => setData(res.data))
      .catch(() => toast.error('Failed to load incidents'))
      .finally(() => setLoading(false));
  }, [statusFilter, lifecycleFilter, opsFilter]);

  useEffect(() => { load(); }, [load]);

  const handleAck = (incidentId) => {
    const note = ackNote[incidentId];
    adminAPI
      .acknowledgeIncident(incidentId, note)
      .then(() => {
        toast.success('Incident acknowledged');
        setAckNote((prev) => ({ ...prev, [incidentId]: undefined }));
        load();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to acknowledge'));
  };

  const handleResolve = (incidentId) => {
    const note = resolveNote[incidentId];
    adminAPI
      .resolveIncident(incidentId, note)
      .then(() => {
        toast.success('Incident resolved');
        setResolveNote((prev) => ({ ...prev, [incidentId]: undefined }));
        load();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to resolve'));
  };

  const formatTime = (iso) => (iso ? new Date(iso).toLocaleString() : '—');
  const severityClass = (s) => (s === 'P0' ? 'bg-red-100 text-red-800' : s === 'P1' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-800');
  const presentationLabelClass = (label) => {
    if (label === 'CRITICAL') return 'bg-red-100 text-red-800';
    if (label === 'ACTION_REQUIRED') return 'bg-amber-100 text-amber-900';
    if (label === 'WARNING') return 'bg-yellow-50 text-yellow-900';
    return 'bg-gray-100 text-gray-800';
  };
  const formatPresentationLabel = (label) => (label ? String(label).replace(/_/g, ' ') : '');

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <AlertTriangle className="w-7 h-7" />
            Incidents
          </h1>
          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatus(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1.5 text-sm"
            >
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
            </select>
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
        </div>

        {loading && !data.items?.length && (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-2 border-indigo-600 border-t-transparent" />
          </div>
        )}

        {data.items && data.items.length === 0 && !loading && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-600">
            <p className="font-medium text-gray-700 mb-1">No incidents found for this filter.</p>
            <p className="text-gray-500">
              {statusFilter === 'open'
                ? 'No open incidents. If automation is healthy, critical jobs are within SLA and the scheduler heartbeat is fresh. Check System Health and Automation Control Centre for job states.'
                : `No ${statusFilter} incidents. Change the filter to see other statuses.`}
            </p>
            <p className="mt-2">
              <Link to="/admin/system-health" className="text-indigo-600 hover:underline">System Health</Link>
              {' · '}
              <Link to="/admin/automation" className="text-indigo-600 hover:underline">Automation Control Centre</Link>
            </p>
          </div>
        )}

        {data.items && data.items.length > 0 && (
          <div className="space-y-4">
            {data.items.map((inc) => {
              const pr = inc.presentation || {};
              const presTitle = pr.presentation_title || inc.title;
              const presSummary = pr.operational_summary || inc.description;
              const resLink = pr.resolution_link || (pr.resolution_links && pr.resolution_links.incident);
              return (
              <div key={inc.id} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      {pr.severity_label ? (
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${presentationLabelClass(pr.severity_label)}`}>
                          {formatPresentationLabel(pr.severity_label)}
                        </span>
                      ) : null}
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityClass(inc.severity)}`} title="Stored severity (audit)">
                        {inc.severity}
                      </span>
                      <span className="text-xs text-gray-500">{inc.status}</span>
                      {(pr.affected_component || inc.related_job_name) && (
                        <span className="text-xs text-gray-500">
                          {pr.affected_component || inc.related_job_name}
                        </span>
                      )}
                    </div>
                    <h3 className="font-medium text-gray-900 mt-1">{presTitle}</h3>
                    <p className="text-sm text-gray-700 mt-1 leading-relaxed">{presSummary}</p>
                    {pr.business_impact && pr.business_impact !== presSummary && (
                      <p className="text-sm text-gray-600 mt-2 border-l-2 border-indigo-200 pl-2">
                        <span className="font-medium text-gray-700">Impact: </span>
                        {pr.business_impact}
                      </p>
                    )}
                    {pr.customer_impact && (
                      <p className="text-sm text-gray-600 mt-1">
                        <span className="font-medium text-gray-700">Customer impact: </span>
                        {pr.customer_impact}
                      </p>
                    )}
                    {pr.recommended_actions && (
                      <p className="text-sm text-indigo-900 bg-indigo-50/80 rounded px-2 py-1.5 mt-2">
                        <span className="font-medium">Recommended: </span>
                        {pr.recommended_actions}
                      </p>
                    )}
                    {resLink && (
                      <p className="mt-2">
                        <Link to={resLink} className="text-sm text-indigo-600 font-medium hover:underline">
                          Open incident
                        </Link>
                        {pr.resolution_links?.observability && pr.resolution_links.observability !== resLink && (
                          <>
                            {' · '}
                            <Link to={pr.resolution_links.observability} className="text-sm text-indigo-600 hover:underline">
                              Observability
                            </Link>
                          </>
                        )}
                        {pr.resolution_links?.automation_centre &&
                          pr.resolution_links.automation_centre !== resLink &&
                          pr.resolution_links.automation_centre !== pr.resolution_links?.observability && (
                            <>
                              {' · '}
                              <Link to={pr.resolution_links.automation_centre} className="text-sm text-indigo-600 hover:underline">
                                Automation Centre
                              </Link>
                            </>
                          )}
                      </p>
                    )}
                    {pr.technical_details && (
                      <details className="mt-3 text-xs text-gray-600">
                        <summary className="cursor-pointer text-gray-500 font-medium">Technical details</summary>
                        <pre className="mt-2 whitespace-pre-wrap bg-gray-50 border border-gray-100 rounded p-2 max-h-48 overflow-auto">
                          {pr.technical_details}
                        </pre>
                      </details>
                    )}
                    <p className="text-xs text-gray-400 mt-2">
                      Created {formatTime(inc.created_at)}
                      {inc.first_detected_at && inc.first_detected_at !== inc.created_at && (
                        <> · First detected {formatTime(inc.first_detected_at)}</>
                      )}
                      {inc.last_detected_at && <> · Last seen {formatTime(inc.last_detected_at)}</>}
                      {inc.recovered_at && <> · Recovered {formatTime(inc.recovered_at)}</>}
                      {inc.acknowledged_by && ` · Acked by ${inc.acknowledged_by} ${formatTime(inc.acknowledged_at)}`}
                      {inc.resolved_by && ` · Resolved by ${inc.resolved_by} ${formatTime(inc.resolved_at)}`}
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 shrink-0">
                    {inc.status === 'open' && (
                      <>
                        <input
                          type="text"
                          placeholder="Note (optional)"
                          value={ackNote[inc.id] || ''}
                          onChange={(e) => setAckNote((prev) => ({ ...prev, [inc.id]: e.target.value }))}
                          className="border border-gray-300 rounded px-2 py-1 text-xs w-40"
                        />
                        <button
                          type="button"
                          onClick={() => handleAck(inc.id)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-amber-100 text-amber-800 rounded hover:bg-amber-200"
                        >
                          <MessageSquare className="w-3 h-3" />
                          Acknowledge
                        </button>
                      </>
                    )}
                    {(inc.status === 'open' || inc.status === 'acknowledged') && (
                      <>
                        <input
                          type="text"
                          placeholder="Resolve note (optional)"
                          value={resolveNote[inc.id] || ''}
                          onChange={(e) => setResolveNote((prev) => ({ ...prev, [inc.id]: e.target.value }))}
                          className="border border-gray-300 rounded px-2 py-1 text-xs w-40"
                        />
                        <button
                          type="button"
                          onClick={() => handleResolve(inc.id)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-green-100 text-green-800 rounded hover:bg-green-200"
                        >
                          <CheckCircle className="w-3 h-3" />
                          Resolve
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
            })}
          </div>
        )}

        <p className="mt-6 text-sm text-gray-500">
          <Link to="/admin/system-health" className="text-indigo-600 hover:underline">System Health</Link>
          {' · '}
          <Link to="/admin/automation" className="text-indigo-600 hover:underline">Automation Control Centre</Link>
        </p>
      </div>
    </UnifiedAdminLayout>
  );
}
