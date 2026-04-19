import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { TrendingUp, RefreshCw, ArrowLeft } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

function Row({ label, value }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-1 sm:gap-4 py-2 border-b border-gray-100 last:border-0">
      <dt className="text-sm font-medium text-gray-600">{label}</dt>
      <dd className="sm:col-span-2 text-sm text-gray-900 font-mono break-all">{String(value)}</dd>
    </div>
  );
}

export default function AdminOpsRoiDiagnosticsPage() {
  const [clientId, setClientId] = useState('');
  const [clients, setClients] = useState([]);
  const [clientsLoading, setClientsLoading] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setClientsLoading(true);
    adminAPI
      .getClients(0, 300)
      .then((res) => setClients(res.data?.clients || res.data?.items || []))
      .catch(() => setClients([]))
      .finally(() => setClientsLoading(false));
  }, []);

  const load = (id) => {
    if (!id) {
      setData(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    adminAPI
      .getClientDashboardRoiDiagnostics(id)
      .then((res) => setData(res.data))
      .catch((err) => {
        setData(null);
        const msg = err?.response?.data?.detail || 'Failed to load ROI diagnostics';
        setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
        toast.error('Failed to load ROI diagnostics');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (clientId) load(clientId);
    else {
      setData(null);
      setError(null);
    }
  }, [clientId]);

  const d = data?.diagnostics || {};

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-3xl">
        <Link
          to="/admin/ops"
          className="inline-flex items-center gap-1 text-sm text-electric-teal hover:underline mb-4"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden />
          Operations overview
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-2">
          <TrendingUp className="w-7 h-7" aria-hidden />
          Client ROI diagnostics
        </h1>
        <p className="text-gray-600 mb-6 text-sm">
          Read-only view of the same month-to-date ROI payload shown on the client dashboard value card, including{' '}
          <code className="text-xs bg-gray-100 px-1 rounded">diagnostics</code> for scan health and jobs without SLA
          deadlines. Use this to judge whether on-time counts are inflated or compliance data failed to load.
        </p>

        <div className="mb-6 flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="roi-client" className="block text-sm font-medium text-gray-700 mb-2">
              Client
            </label>
            <select
              id="roi-client"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm w-full max-w-md"
              disabled={clientsLoading}
            >
              <option value="">— Select client —</option>
              {clients.map((c) => (
                <option key={c.client_id} value={c.client_id}>
                  {c.name || c.company_name || c.client_id}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => clientId && load(clientId)}
            disabled={!clientId || loading}
            className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={loading ? 'animate-spin w-4 h-4' : 'w-4 h-4'} aria-hidden />
            Refresh
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 mb-4 text-sm">{error}</div>
        )}

        {loading && !data && clientId && (
          <div className="flex justify-center py-10">
            <div className="animate-spin rounded-full h-10 w-10 border-2 border-electric-teal border-t-transparent" />
          </div>
        )}

        {data && (
          <div className="space-y-6">
            {data.unavailable && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 text-sm">
                Payload marked <strong>unavailable</strong> — client UI would show zeros; check server logs for the
                underlying error.
              </div>
            )}

            <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">Summary (client-visible numbers)</h2>
              <dl>
                <Row label="client_id" value={data.client_id} />
                <Row label="period_label" value={data.period_label} />
                <Row label="period_start" value={data.period_start} />
                <Row label="period_end" value={data.period_end} />
                <Row label="compliance_items_up_to_date" value={data.compliance_items_up_to_date} />
                <Row label="compliance_basis" value={data.compliance_basis} />
                <Row label="jobs_completed_on_time" value={data.jobs_completed_on_time} />
                <Row label="jobs_completed_in_period" value={data.jobs_completed_in_period} />
                <Row label="sla_breaches_avoided" value={data.sla_breaches_avoided} />
                <Row label="approximate" value={String(data.approximate)} />
              </dl>
            </section>

            <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">Diagnostics (ops only)</h2>
              <dl>
                <Row label="requirements_scan_ok" value={String(d.requirements_scan_ok)} />
                <Row label="work_orders_scan_ok" value={String(d.work_orders_scan_ok)} />
                <Row
                  label="jobs_in_period_without_sla_deadline"
                  value={d.jobs_in_period_without_sla_deadline ?? '—'}
                />
                <Row
                  label="jobs_on_time_without_sla_deadline"
                  value={d.jobs_on_time_without_sla_deadline ?? '—'}
                />
                {d.endpoint_error != null && <Row label="endpoint_error" value={String(d.endpoint_error)} />}
              </dl>
              <p className="text-xs text-gray-500 mt-3">
                High <code className="bg-gray-100 px-1 rounded">jobs_on_time_without_sla_deadline</code> relative to
                on-time total suggests the client &quot;on time&quot; headline may be inflated (v1 treats missing SLA
                targets as on-time).
              </p>
            </section>
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
