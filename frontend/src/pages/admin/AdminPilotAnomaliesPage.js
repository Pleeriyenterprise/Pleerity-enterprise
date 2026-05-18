import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader2, RefreshCw, Wrench } from 'lucide-react';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { toast } from '@/utils/portalNotifications';
import { useAuth } from '../../contexts/AuthContext';
import PilotReasonDialog from '../../components/admin/pilot/PilotReasonDialog';
import { apiErrorMessage, severityClass } from '../../utils/pilotOperationsAdmin';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch {
    return String(iso);
  }
}

const SEVERITIES = ['critical', 'warning', 'info'];

export default function AdminPilotAnomaliesPage() {
  const { isAdmin, isOwner } = useAuth();
  const canManage = Boolean(isAdmin?.() || isOwner?.());

  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [severity, setSeverity] = useState('');
  const [resolveTarget, setResolveTarget] = useState(null);
  const [reconcileBusy, setReconcileBusy] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminAPI.listPilotLifecycleAnomalies({ limit: 500 });
      setAnomalies(res.data?.anomalies || []);
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to load anomalies'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canManage) load();
  }, [canManage, load]);

  const filtered = useMemo(() => {
    let rows = anomalies || [];
    if (severity) rows = rows.filter((a) => (a.severity || '').toLowerCase() === severity);
    const q = search.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (a) =>
          a.client_id?.toLowerCase().includes(q) ||
          a.anomaly_code?.toLowerCase().includes(q) ||
          a.message?.toLowerCase().includes(q),
      );
    }
    return rows;
  }, [anomalies, severity, search]);

  const runReconcile = async (clientId) => {
    setReconcileBusy(clientId);
    try {
      await adminAPI.reconcilePilotLifecycleAccount(clientId);
      toast.success('Reconciliation complete');
      await load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setReconcileBusy(null);
    }
  };

  if (!canManage) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">
          <Alert>
            <AlertDescription>Owner or admin access required.</AlertDescription>
          </Alert>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-5xl mx-auto space-y-6" data-testid="admin-pilot-anomalies-page">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/admin/pilot-operations">
              <ArrowLeft className="h-4 w-4 mr-1" /> Operations
            </Link>
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-midnight-blue">Pilot anomalies</h1>
            <p className="text-sm text-gray-600 mt-1">Open operational anomalies across founding pilot accounts.</p>
          </div>
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
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

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Open anomalies ({filtered.length})</CardTitle>
            <div className="flex flex-wrap gap-2 mt-2">
              <Input
                placeholder="Search client, code, message…"
                className="max-w-xs h-9 text-sm"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                data-testid="anomaly-search"
              />
              <select
                className="border rounded px-2 py-1 text-sm"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                <option value="">All severities</option>
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-gray-500 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading…
              </p>
            ) : (
              <div className="space-y-3" data-testid="anomaly-list">
                {filtered.map((a) => (
                  <div key={a.anomaly_id} className="border rounded p-4 text-sm">
                    <div className="flex flex-wrap justify-between gap-2">
                      <div>
                        <span className={`px-2 py-0.5 rounded text-xs ${severityClass(a.severity)}`}>
                          {a.severity}
                        </span>
                        <span className="ml-2 font-mono text-xs">{a.anomaly_code}</span>
                        <p className="text-gray-700 mt-2">{a.message}</p>
                        <p className="text-xs text-gray-500 mt-1">
                          Client: {a.client_id} · Detected {formatDate(a.detected_at)}
                          {a.last_detected_at && a.last_detected_at !== a.detected_at
                            ? ` · Last seen ${formatDate(a.last_detected_at)}`
                            : ''}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 items-start">
                        <Button size="sm" variant="outline" asChild>
                          <Link to={`/admin/pilot-operations/accounts/${encodeURIComponent(a.client_id)}`}>
                            View account
                          </Link>
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={reconcileBusy === a.client_id}
                          onClick={() => runReconcile(a.client_id)}
                        >
                          <Wrench className="h-3 w-3 mr-1" />
                          {reconcileBusy === a.client_id ? 'Reconciling…' : 'Reconcile'}
                        </Button>
                        <Button
                          size="sm"
                          onClick={() =>
                            setResolveTarget({
                              anomalyId: a.anomaly_id,
                              code: a.anomaly_code,
                            })
                          }
                        >
                          Resolve
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
                {!filtered.length && (
                  <p className="text-sm text-gray-500 py-8 text-center">No open anomalies match filters.</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <PilotReasonDialog
          open={Boolean(resolveTarget)}
          onOpenChange={(o) => !o && setResolveTarget(null)}
          title="Resolve anomaly"
          description={resolveTarget?.code}
          onConfirm={async ({ reason }) => {
            await adminAPI.resolvePilotLifecycleAnomaly(resolveTarget.anomalyId, {
              resolution_notes: reason,
            });
            toast.success('Anomaly resolved');
            await load();
          }}
        />
      </div>
    </UnifiedAdminLayout>
  );
}
