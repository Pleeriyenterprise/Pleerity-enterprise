import React, { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Shield, RefreshCw, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

function MetricCard({ title, value }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-xs text-gray-500">{title}</div>
      <div className="mt-1 text-2xl font-semibold text-gray-900">{value ?? 0}</div>
    </div>
  );
}

export default function AdminSecurityDashboardPage() {
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [incidents, setIncidents] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, e, i] = await Promise.all([
        adminAPI.getSecurityDashboard({ days }),
        adminAPI.getSecurityEvents({ limit: 50 }),
        adminAPI.getSecurityIncidents({ status: 'open', limit: 50 }),
      ]);
      setSummary(s?.data || null);
      setEvents(e?.data?.items || []);
      setIncidents(i?.data?.items || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load security dashboard');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  const resolveIncident = async (incidentKey) => {
    try {
      await adminAPI.resolveSecurityIncident(incidentKey, 'Resolved from security dashboard');
      toast.success('Incident resolved');
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to resolve incident');
    }
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-7xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="w-7 h-7" />
            Security Monitoring
          </h1>
          <div className="flex items-center gap-2">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value={1}>Last 24h</option>
              <option value={7}>Last 7d</option>
              <option value={30}>Last 30d</option>
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

        {summary && (
          <div className="space-y-6">
            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Authentication activity</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <MetricCard title="Successful logins" value={summary.authentication_activity?.successful_logins} />
                <MetricCard title="Failed attempts" value={summary.authentication_activity?.failed_attempts} />
                <MetricCard title="Password resets" value={summary.authentication_activity?.password_resets} />
              </div>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Access control</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <MetricCard title="Admin route attempts" value={summary.access_control?.admin_route_access_attempts} />
                <MetricCard title="Denied requests" value={summary.access_control?.denied_requests} />
                <MetricCard title="Role violations" value={summary.access_control?.role_violations} />
              </div>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">API abuse</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <MetricCard title="Rate limit hits" value={summary.api_abuse?.rate_limit_hits} />
                <MetricCard title="Request spikes" value={summary.api_abuse?.request_spikes} />
                <MetricCard title="Malformed requests" value={summary.api_abuse?.malformed_requests} />
              </div>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Payment/Webhook integrity</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <MetricCard title="Stripe signature failures" value={summary.payment_webhook_integrity?.stripe_signature_failures} />
                <MetricCard title="Duplicate webhook detection" value={summary.payment_webhook_integrity?.duplicate_webhook_detection} />
                <MetricCard title="Rejected events" value={summary.payment_webhook_integrity?.rejected_events} />
              </div>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">File/document access</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <MetricCard title="Downloads" value={summary.file_document_access?.downloads} />
                <MetricCard title="Failed access" value={summary.file_document_access?.failed_access} />
                <MetricCard title="Cross-user attempts" value={summary.file_document_access?.cross_user_access_attempts} />
              </div>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">System integrity</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <MetricCard title="JWT failures" value={summary.system_integrity?.jwt_validation_failures} />
                <MetricCard title="Token misuse" value={summary.system_integrity?.token_misuse} />
                <MetricCard title="Invalid sessions" value={summary.system_integrity?.invalid_sessions} />
              </div>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Threat detections</h2>
              <p className="text-sm text-gray-600 mb-3">
                Counts are distinct incident records opened or updated in the selected period (deduplicated by principal until resolved).
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
                <MetricCard title="Brute force login" value={summary.threat_detections?.brute_force_login} />
                <MetricCard title="Rapid failed auth" value={summary.threat_detections?.rapid_failed_auth} />
                <MetricCard title="Token reuse multi-IP" value={summary.threat_detections?.token_reuse_multi_ip} />
                <MetricCard title="Suspicious data access mass download" value={summary.threat_detections?.suspicious_data_access_pattern} />
                <MetricCard title="Cross-user data access probe" value={summary.threat_detections?.cross_user_data_access_probe} />
                <MetricCard title="Endpoint probing" value={summary.threat_detections?.endpoint_probing} />
                <MetricCard title="Admin route request spike" value={summary.threat_detections?.admin_route_request_spike} />
                <MetricCard title="Webhook signature attack" value={summary.threat_detections?.webhook_signature_attack} />
                <MetricCard title="Malformed spikes" value={summary.threat_detections?.malformed_request_spike} />
              </div>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Auto response</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <MetricCard title="Active temporary locks" value={summary.auto_response?.active_temporary_locks} />
                <MetricCard title="Active IP blocks" value={summary.auto_response?.active_ip_blocks} />
                <MetricCard title="Token invalidations" value={summary.auto_response?.token_invalidations} />
              </div>
            </section>
          </div>
        )}

        <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
          <section className="bg-white border border-gray-200 rounded-lg">
            <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Open Security Incidents</h3>
              <span className="text-sm text-gray-500">{incidents.length}</span>
            </div>
            <div className="max-h-[420px] overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left">Type</th>
                    <th className="px-3 py-2 text-left">Severity</th>
                    <th className="px-3 py-2 text-left">User</th>
                    <th className="px-3 py-2 text-left">Time</th>
                    <th className="px-3 py-2 text-left">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {incidents.length === 0 && (
                    <tr><td className="px-3 py-3 text-gray-500" colSpan={5}>No open incidents</td></tr>
                  )}
                  {incidents.map((row) => (
                    <tr key={row.incident_key}>
                      <td className="px-3 py-2 font-medium">{row.type}</td>
                      <td className="px-3 py-2">{row.severity}</td>
                      <td className="px-3 py-2 text-gray-600 font-mono text-xs">{row.user_id || '—'}</td>
                      <td className="px-3 py-2 text-gray-600">{row.timestamp ? new Date(row.timestamp).toLocaleString() : '—'}</td>
                      <td className="px-3 py-2">
                        <button type="button" onClick={() => resolveIncident(row.incident_key)} className="text-indigo-600 hover:underline">Resolve</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="bg-white border border-gray-200 rounded-lg">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="font-semibold text-gray-900">Recent Security Events</h3>
            </div>
            <div className="max-h-[420px] overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left">Event</th>
                    <th className="px-3 py-2 text-left">Severity</th>
                    <th className="px-3 py-2 text-left">User</th>
                    <th className="px-3 py-2 text-left">IP</th>
                    <th className="px-3 py-2 text-left">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {events.length === 0 && (
                    <tr><td className="px-3 py-3 text-gray-500" colSpan={5}>No events yet</td></tr>
                  )}
                  {events.map((row) => (
                    <tr key={row.event_id}>
                      <td className="px-3 py-2 font-medium">{row.event_type}</td>
                      <td className="px-3 py-2">{row.severity}</td>
                      <td className="px-3 py-2 text-gray-600 font-mono text-xs">{row.user_id || '—'}</td>
                      <td className="px-3 py-2">{row.ip || '—'}</td>
                      <td className="px-3 py-2 text-gray-600">{row.timestamp ? new Date(row.timestamp).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {summary?.incidents?.open > 0 && (
          <div className="mt-6 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            {summary.incidents.open} security incident(s) currently open.
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
