import React, { useState, useEffect } from 'react';
import { adminAPI } from '../../api/client';
import { useAuth } from '../../contexts/AuthContext';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Zap, RefreshCw, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminOpsFeatureControlsPage() {
  const { user } = useAuth();
  const isReadOnly = user?.role === 'ROLE_AUDITOR';
  const [clientId, setClientId] = useState('');
  const [clients, setClients] = useState([]);
  const [clientsLoading, setClientsLoading] = useState(false);
  const [flagsData, setFlagsData] = useState(null);
  const [planUsage, setPlanUsage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setClientsLoading(true);
    adminAPI
      .getClients(0, 200)
      .then((res) => setClients(res.data?.clients || res.data?.items || []))
      .catch(() => setClients([]))
      .finally(() => setClientsLoading(false));
  }, []);

  const loadClient = (id) => {
    if (!id) {
      setFlagsData(null);
      setPlanUsage(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([
      adminAPI.getClientFeatureFlags(id),
      adminAPI.getClientPlanUsage(id),
    ])
      .then(([flagsRes, usageRes]) => {
        setFlagsData(flagsRes.data);
        setPlanUsage(usageRes.data);
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load client');
        setFlagsData(null);
        setPlanUsage(null);
        toast.error('Failed to load client');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (clientId) loadClient(clientId);
    else {
      setFlagsData(null);
      setPlanUsage(null);
    }
  }, [clientId]);

  const handleToggle = (flagKey, enabled) => {
    if (!clientId || !flagsData?.flags) return;
    setSaving(true);
    adminAPI
      .updateClientFeatureFlags(clientId, [{ flag_key: flagKey, enabled }])
      .then(() => {
        toast.success('Feature flag updated');
        loadClient(clientId);
      })
      .catch((err) => {
        toast.error(err?.response?.data?.detail || 'Update failed');
      })
      .finally(() => setSaving(false));
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-4xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-6">
          <Zap className="w-7 h-7" />
          Feature Controls
        </h1>
        <p className="text-gray-600 mb-6">
          {isReadOnly
            ? 'View module feature flags per client (read-only). Only Owner/Admin can change flags.'
            : 'View and update module feature flags per client. Defaults are derived from plan; overrides are stored per client. Only Owner/Admin can change flags.'}
        </p>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Select client</label>
          <div className="flex gap-2">
            <select
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm w-full max-w-md"
              disabled={clientsLoading}
            >
              <option value="">— Select client —</option>
              {clients.map((c) => (
                <option key={c.client_id} value={c.client_id}>
                  {c.customer_reference || c.client_id} — {c.full_name || c.email || c.contact_email || '—'}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => loadClient(clientId)}
              disabled={!clientId || loading}
              className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 mb-4">{error}</div>
        )}

        {planUsage && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 mb-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-2">Plan usage</h2>
            <p className="text-sm text-gray-600">
              Plan: <strong>{planUsage.plan_name || planUsage.billing_plan}</strong>
              {' · '}
              Properties: <strong>{planUsage.properties_used}</strong> / {planUsage.properties_allowed}
              {planUsage.properties_at_limit && <span className="text-amber-600 ml-1">(at limit)</span>}
              {' · '}
              Seats used: {planUsage.seats_used ?? 0}
              {planUsage.seats_allowed != null && ` / ${planUsage.seats_allowed}`}
            </p>
          </div>
        )}

        {flagsData?.flags && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Module flags</h2>
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Module</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Status</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Source</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Action</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {flagsData.flags.map((f) => (
                    <tr key={f.flag_key}>
                      <td className="px-4 py-2 text-sm text-gray-900">{f.label}</td>
                      <td className="px-4 py-2">
                        <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${f.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                          {f.enabled ? 'On' : 'Off'}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-500">{f.source || '—'}</td>
                      <td className="px-4 py-2">
                        {!isReadOnly ? (
                          <button
                            type="button"
                            onClick={() => handleToggle(f.flag_key, !f.enabled)}
                            disabled={saving}
                            className="text-sm text-electric-teal hover:underline disabled:opacity-50"
                          >
                            {f.enabled ? 'Turn off' : 'Turn on'}
                          </button>
                        ) : (
                          <span className="text-sm text-gray-400">View only</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {clientId && !loading && !flagsData?.flags?.length && !error && (
          <p className="text-gray-500 text-sm">No flag data for this client.</p>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
