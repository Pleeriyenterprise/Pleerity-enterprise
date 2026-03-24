import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';

function formatTs(v) {
  if (!v) return '—';
  try {
    return new Date(v).toLocaleString();
  } catch {
    return String(v);
  }
}

export default function AdminOpsAuditPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [skip, setSkip] = useState(0);
  const limit = 50;
  const [draftClientId, setDraftClientId] = useState('');
  const [draftAction, setDraftAction] = useState('');
  const [draftStart, setDraftStart] = useState('');
  const [draftEnd, setDraftEnd] = useState('');
  const [filters, setFilters] = useState({ client_id: '', action: '', start_date: '', end_date: '' });
  const [actions, setActions] = useState([]);

  const applyFilters = () => {
    setSkip(0);
    setFilters({
      client_id: draftClientId.trim(),
      action: draftAction.trim(),
      start_date: draftStart.trim(),
      end_date: draftEnd.trim(),
    });
  };

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    adminAPI
      .getAuditLogs({
        skip,
        limit,
        client_id: filters.client_id || undefined,
        action: filters.action || undefined,
        start_date: filters.start_date || undefined,
        end_date: filters.end_date || undefined,
      })
      .then((res) => {
        setLogs(res.data?.logs || []);
        setTotal(res.data?.total ?? 0);
        const avail = res.data?.filters?.available_actions;
        if (Array.isArray(avail) && avail.length) setActions(avail);
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load audit logs');
        setLogs([]);
      })
      .finally(() => setLoading(false));
  }, [skip, filters]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Ops — Audit events</h1>
        <p className="text-gray-600 text-sm mb-4 max-w-3xl">
          Filterable view of <code className="text-xs bg-gray-100 px-1 rounded">audit_logs</code>. Use the main admin dashboard
          for CSV export and advanced views. Client audit log (client portal) is separate.
        </p>
        <div className="flex flex-wrap gap-4 mb-6 text-sm">
          <Link to="/admin/ops" className="text-electric-teal hover:underline">
            ← Ops overview
          </Link>
          <Link to="/admin" className="text-electric-teal hover:underline">
            Main admin dashboard
          </Link>
          <Link to="/admin/automation" className="text-electric-teal hover:underline">
            Automation & job runs
          </Link>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Client ID</label>
            <input
              value={draftClientId}
              onChange={(e) => setDraftClientId(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Optional"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Action</label>
            <select
              value={draftAction}
              onChange={(e) => setDraftAction(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">Any</option>
              {actions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Start date</label>
            <input
              type="date"
              value={draftStart}
              onChange={(e) => setDraftStart(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">End date</label>
            <input
              type="date"
              value={draftEnd}
              onChange={(e) => setDraftEnd(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="flex gap-2 mb-4">
          <Button type="button" size="sm" onClick={applyFilters} disabled={loading}>
            Apply filters
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={load} disabled={loading}>
            Refresh
          </Button>
          <span className="text-xs text-gray-500 self-center">
            {total} total · showing {logs.length}
          </span>
        </div>

        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}
        {loading ? (
          <p className="text-gray-500 text-sm">Loading…</p>
        ) : (
          <>
            <div className="overflow-x-auto border border-gray-200 rounded-lg mb-4">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="p-2">Time</th>
                    <th className="p-2">Action</th>
                    <th className="p-2">Actor</th>
                    <th className="p-2">Client</th>
                    <th className="p-2">Resource</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-4 text-gray-500">
                        No events for this filter.
                      </td>
                    </tr>
                  ) : (
                    logs.map((row, i) => (
                      <tr key={row.id || row._id || `${row.timestamp}-${i}`} className="border-t border-gray-100">
                        <td className="p-2 whitespace-nowrap text-gray-700">{formatTs(row.timestamp)}</td>
                        <td className="p-2 font-mono text-xs">{row.action || '—'}</td>
                        <td className="p-2 text-xs">{row.actor_id || row.user_id || '—'}</td>
                        <td className="p-2 text-xs">{row.client_id || '—'}</td>
                        <td className="p-2 text-xs">
                          {(row.resource_type || '') + (row.resource_id ? ` / ${row.resource_id}` : '')}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex gap-2">
              <Button type="button" size="sm" variant="outline" disabled={skip <= 0 || loading} onClick={() => setSkip((s) => Math.max(0, s - limit))}>
                Previous
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={skip + limit >= total || loading}
                onClick={() => setSkip((s) => s + limit)}
              >
                Next
              </Button>
            </div>
          </>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
