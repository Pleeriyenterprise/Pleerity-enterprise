import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { AlertTriangle, RefreshCw, CheckCircle, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';

const VALID_STATUS = ['open', 'acknowledged', 'resolved'];

export default function AdminIncidentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFromUrl = searchParams.get('status');
  const initialStatus = statusFromUrl && VALID_STATUS.includes(statusFromUrl) ? statusFromUrl : 'open';
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(initialStatus);
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
  }, [searchParams]);

  const load = () => {
    setLoading(true);
    adminAPI
      .getIncidents({ status: statusFilter, limit: 50 })
      .then((res) => setData(res.data))
      .catch(() => toast.error('Failed to load incidents'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [statusFilter]);

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
          <p className="text-gray-500 py-8">No incidents found for this filter.</p>
        )}

        {data.items && data.items.length > 0 && (
          <div className="space-y-4">
            {data.items.map((inc) => (
              <div key={inc.id} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityClass(inc.severity)}`}>
                        {inc.severity}
                      </span>
                      <span className="text-xs text-gray-500">{inc.status}</span>
                      {inc.related_job_name && <span className="text-xs text-gray-400 font-mono">{inc.related_job_name}</span>}
                    </div>
                    <h3 className="font-medium text-gray-900 mt-1">{inc.title}</h3>
                    <p className="text-sm text-gray-600 mt-1">{inc.description}</p>
                    <p className="text-xs text-gray-400 mt-2">
                      Created {formatTime(inc.created_at)}
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
            ))}
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
