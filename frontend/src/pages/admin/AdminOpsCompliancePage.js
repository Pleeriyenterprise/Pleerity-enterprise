import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';

function formatWhen(v) {
  if (!v) return '—';
  try {
    return new Date(v).toLocaleString();
  } catch {
    return String(v);
  }
}

export default function AdminOpsCompliancePage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [clientFilter, setClientFilter] = useState('');
  const [clients, setClients] = useState([]);

  useEffect(() => {
    adminAPI
      .getClients(0, 500)
      .then((res) => {
        const list = res.data?.clients || res.data?.items || [];
        setClients(Array.isArray(list) ? list : []);
      })
      .catch(() => setClients([]));
  }, []);

  const load = () => {
    setLoading(true);
    setError('');
    adminAPI
      .getComplianceClientsSummary({ client_id: clientFilter.trim() || undefined, limit: 300 })
      .then((res) => setRows(res.data?.rows || []))
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load summary');
        setRows([]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientFilter]);

  const sortedRows = useMemo(() => [...rows], [rows]);

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Client requirement status</h1>
        <p className="text-gray-600 text-sm mb-6 max-w-3xl">
          Requirement-level counts per client (overdue and expiring soon). This is a <strong>coverage / workload</strong> view — not the same as{' '}
          <Link to="/admin/ops/risk" className="text-electric-teal hover:underline">Risk &amp; Insights</Link> (signals) or{' '}
          <Link to="/admin/ops/audit" className="text-electric-teal hover:underline">Portfolio compliance audit</Link> (audit trail).
          Clients appear if they have at least one requirement document in the database. When you filter to one client, portfolio score is calculated on demand.
        </p>
        <div className="flex flex-wrap items-end gap-3 mb-6">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Client</label>
            <select
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm min-w-[220px] bg-white"
            >
              <option value="">All clients (from requirements)</option>
              {clients.map((c) => (
                <option key={c.client_id} value={c.client_id}>
                  {(c.company_name || c.full_name || c.client_id) + ` (${c.client_id})`}
                </option>
              ))}
            </select>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
            Refresh
          </Button>
          <Link to="/admin/ops" className="text-sm text-electric-teal hover:underline self-center">
            ← Ops overview
          </Link>
          <Link to="/admin/ops/risk" className="text-sm text-electric-teal hover:underline self-center">
            Risk dashboard
          </Link>
          <Link to="/admin/ops/action-links" className="text-sm text-electric-teal hover:underline self-center">
            Action links overrides
          </Link>
          <Link to="/admin/compliance/registry" className="text-sm text-electric-teal hover:underline self-center">
            Requirement Registry
          </Link>
        </div>
        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}
        {loading ? (
          <p className="text-gray-500 text-sm">Loading…</p>
        ) : (
          <div className="overflow-x-auto border border-gray-200 rounded-lg">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="p-3">Client</th>
                  <th className="p-3">Overdue</th>
                  <th className="p-3">Expiring soon</th>
                  <th className="p-3">Requirements updated</th>
                  <th className="p-3">Score / grade</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody>
                {sortedRows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-4 text-gray-500">
                      No rows. Try clearing the client filter or confirm requirements exist in Mongo.
                    </td>
                  </tr>
                ) : (
                  sortedRows.map((r) => (
                    <tr key={r.client_id} className="border-t border-gray-100 hover:bg-gray-50/80">
                      <td className="p-3 font-medium text-gray-900">{r.client_name || r.client_id}</td>
                      <td className="p-3 tabular-nums">{r.overdue_count}</td>
                      <td className="p-3 tabular-nums">{r.expiring_soon_count}</td>
                      <td className="p-3 text-gray-600 whitespace-nowrap">{formatWhen(r.requirements_last_updated)}</td>
                      <td className="p-3">
                        {r.portfolio_score != null ? (
                          <span>
                            {r.portfolio_score}/100 · Grade {r.portfolio_grade || '—'}
                          </span>
                        ) : (
                          <span className="text-gray-400">Filter one client for score</span>
                        )}
                      </td>
                      <td className="p-3 text-right">
                        <Link
                          to={`/admin/clients/${r.client_id}`}
                          className="text-electric-teal hover:underline text-xs font-medium"
                        >
                          Open client
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
