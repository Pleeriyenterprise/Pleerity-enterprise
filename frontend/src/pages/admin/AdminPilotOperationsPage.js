import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  RefreshCw,
  Loader2,
  ExternalLink,
  AlertTriangle,
  Activity,
  Users,
  CreditCard,
  TrendingUp,
} from 'lucide-react';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { toast } from '@/utils/portalNotifications';
import { useAuth } from '../../contexts/AuthContext';
import {
  BILLING_STATUSES,
  ENTITLEMENT_STATUSES,
  GOVERNANCE_STATUSES,
  HEALTH_BANDS,
  apiErrorMessage,
  computeOpsMetrics,
  filterPilotAccounts,
  healthBandClass,
  sortPilotAccounts,
} from '../../utils/pilotOperationsAdmin';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch {
    return String(iso);
  }
}

function MetricCard({ label, value, icon: Icon, highlight }) {
  return (
    <Card className={highlight ? 'border-amber-300 bg-amber-50/50' : ''}>
      <CardContent className="pt-4 pb-3">
        <div className="flex items-center justify-between">
          <p className="text-xs text-gray-600 uppercase tracking-wide">{label}</p>
          {Icon && <Icon className="h-4 w-4 text-gray-400" />}
        </div>
        <p className="text-2xl font-semibold mt-1" data-testid={`metric-${label.replace(/\s+/g, '-')}`}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

export default function AdminPilotOperationsPage() {
  const { isAdmin, isOwner } = useAuth();
  const canManage = Boolean(isAdmin?.() || isOwner?.());

  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({
    governance: '',
    billing: '',
    entitlement: '',
    health_band: '',
    conversion_ready: false,
    missing_pm: false,
    has_anomalies: false,
    nearing_expiry: false,
    converted: false,
    comped: false,
    inactive: false,
  });
  const [sortKey, setSortKey] = useState('days_remaining');
  const [sortDir, setSortDir] = useState('asc');
  const [page, setPage] = useState(0);
  const pageSize = 25;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminAPI.getPilotLifecycleOpsDashboard({ limit: 500 });
      setAccounts(res.data?.accounts || []);
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to load pilot operations'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canManage) load();
  }, [canManage, load]);

  const metrics = useMemo(() => computeOpsMetrics(accounts), [accounts]);

  const filtered = useMemo(() => {
    const f = { ...filters };
    if (f.conversion_ready) f.conversion_ready = true;
    return filterPilotAccounts(accounts, f, search);
  }, [accounts, filters, search]);

  const sorted = useMemo(() => sortPilotAccounts(filtered, sortKey, sortDir), [filtered, sortKey, sortDir]);

  const pageRows = useMemo(() => {
    const start = page * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, page]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const SortTh = ({ k, children }) => (
    <th className="py-2 pr-3 cursor-pointer hover:text-midnight-blue" onClick={() => toggleSort(k)}>
      {children}
      {sortKey === k ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
    </th>
  );

  if (!canManage) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">
          <Alert>
            <AlertDescription>Owner or admin access is required for pilot operations.</AlertDescription>
          </Alert>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-[1400px] mx-auto space-y-6" data-testid="admin-pilot-operations-page">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-midnight-blue">Founding Pilot Operations</h1>
            <p className="text-sm text-gray-600 mt-1">
              Monitor active pilot accounts, health, conversion readiness, and anomalies.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <Link to="/admin/pilot-operations/anomalies">
                <AlertTriangle className="h-4 w-4 mr-2" />
                Anomalies ({metrics.open_anomalies})
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/admin/pilot-invites">Pilot invites</Link>
            </Button>
            <Button variant="outline" onClick={load} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {error}
              <Button variant="link" className="ml-2 p-0 h-auto" onClick={load}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="pilot-ops-metrics">
          <MetricCard label="Active pilots" value={metrics.active} icon={Users} />
          <MetricCard label="Nearing expiry" value={metrics.nearing_expiry} icon={Activity} highlight />
          <MetricCard label="Conversion ready" value={metrics.conversion_ready} icon={TrendingUp} />
          <MetricCard label="Missing PM" value={metrics.missing_payment_method} icon={CreditCard} highlight />
          <MetricCard label="Open anomalies" value={metrics.open_anomalies} icon={AlertTriangle} highlight />
          <MetricCard label="At risk" value={metrics.at_risk} />
          <MetricCard label="Healthy" value={metrics.healthy} />
          <MetricCard label="Converted" value={metrics.converted} />
          <MetricCard label="Comped" value={metrics.comped} />
          <MetricCard label="With anomalies" value={metrics.with_anomalies} />
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Pilot accounts</CardTitle>
            <div className="flex flex-wrap gap-2 mt-3">
              <Input
                placeholder="Search name, email, client ID, invite…"
                className="max-w-xs h-9 text-sm"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0);
                }}
                data-testid="pilot-ops-search"
              />
              <select
                className="border rounded px-2 py-1 text-sm"
                value={filters.governance}
                onChange={(e) => setFilters((f) => ({ ...f, governance: e.target.value }))}
              >
                <option value="">All governance</option>
                {GOVERNANCE_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <select
                className="border rounded px-2 py-1 text-sm"
                value={filters.billing}
                onChange={(e) => setFilters((f) => ({ ...f, billing: e.target.value }))}
              >
                <option value="">All billing</option>
                {BILLING_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <select
                className="border rounded px-2 py-1 text-sm"
                value={filters.entitlement}
                onChange={(e) => setFilters((f) => ({ ...f, entitlement: e.target.value }))}
              >
                <option value="">All entitlement</option>
                {ENTITLEMENT_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <select
                className="border rounded px-2 py-1 text-sm"
                value={filters.health_band}
                onChange={(e) => setFilters((f) => ({ ...f, health_band: e.target.value }))}
              >
                <option value="">All health</option>
                {HEALTH_BANDS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={filters.missing_pm}
                  onChange={(e) => setFilters((f) => ({ ...f, missing_pm: e.target.checked }))}
                />
                Missing PM
              </label>
              <label className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={filters.has_anomalies}
                  onChange={(e) => setFilters((f) => ({ ...f, has_anomalies: e.target.checked }))}
                />
                Has anomalies
              </label>
              <label className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={filters.nearing_expiry}
                  onChange={(e) => setFilters((f) => ({ ...f, nearing_expiry: e.target.checked }))}
                />
                Nearing expiry
              </label>
              <label className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={filters.conversion_ready}
                  onChange={(e) => setFilters((f) => ({ ...f, conversion_ready: e.target.checked }))}
                />
                Conversion ready
              </label>
              <label className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={filters.converted}
                  onChange={(e) => setFilters((f) => ({ ...f, converted: e.target.checked }))}
                />
                Converted
              </label>
              <label className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={filters.comped}
                  onChange={(e) => setFilters((f) => ({ ...f, comped: e.target.checked }))}
                />
                Comped
              </label>
              <label className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={filters.inactive}
                  onChange={(e) => setFilters((f) => ({ ...f, inactive: e.target.checked }))}
                />
                Inactive
              </label>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-gray-500 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading pilot accounts…
              </p>
            ) : (
              <>
                <p className="text-xs text-gray-500 mb-2">
                  Showing {pageRows.length} of {sorted.length} (total loaded {accounts.length})
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="pilot-ops-table">
                    <thead>
                      <tr className="border-b text-left text-gray-600">
                        <SortTh k="name">Account</SortTh>
                        <th className="py-2 pr-3">Plan</th>
                        <th className="py-2 pr-3">Governance</th>
                        <th className="py-2 pr-3">Billing</th>
                        <th className="py-2 pr-3">Entitlement</th>
                        <SortTh k="health_score">Health</SortTh>
                        <SortTh k="days_remaining">Days left</SortTh>
                        <th className="py-2 pr-3">PM</th>
                        <th className="py-2 pr-3">Anomalies</th>
                        <th className="py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {pageRows.map((r) => (
                        <tr key={r.client_id} className="border-b hover:bg-slate-50">
                          <td className="py-2 pr-3">
                            <div className="font-medium">{r.name}</div>
                            <div className="text-xs text-gray-500">{r.email}</div>
                          </td>
                          <td className="py-2 pr-3 text-xs">{r.billing_plan}</td>
                          <td className="py-2 pr-3">
                            <span className="text-xs">{r.governance || r.pilot_status}</span>
                          </td>
                          <td className="py-2 pr-3 text-xs">{r.billing || '—'}</td>
                          <td className="py-2 pr-3 text-xs">{r.entitlement || '—'}</td>
                          <td className="py-2 pr-3">
                            <span className={`px-2 py-0.5 rounded text-xs ${healthBandClass(r.health_band)}`}>
                              {r.health_band || '—'}
                              {r.health_score != null ? ` (${r.health_score})` : ''}
                            </span>
                          </td>
                          <td className="py-2 pr-3">{r.days_remaining ?? '—'}</td>
                          <td className="py-2 pr-3">{r.payment_method_collected ? 'Yes' : 'No'}</td>
                          <td className="py-2 pr-3">
                            {r.anomaly_count > 0 ? (
                              <span className="text-amber-700 font-medium">{r.anomaly_count}</span>
                            ) : (
                              '0'
                            )}
                          </td>
                          <td className="py-2">
                            <Button size="sm" variant="ghost" asChild>
                              <Link to={`/admin/pilot-operations/accounts/${encodeURIComponent(r.client_id)}`}>
                                <ExternalLink className="h-3 w-3" />
                              </Link>
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!pageRows.length && (
                    <p className="text-sm text-gray-500 py-8 text-center">No pilot accounts match filters.</p>
                  )}
                </div>
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-4">
                    <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                      Previous
                    </Button>
                    <span className="text-xs text-gray-600">
                      Page {page + 1} / {totalPages}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={page >= totalPages - 1}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
}
