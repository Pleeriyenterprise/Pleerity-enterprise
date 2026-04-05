import React, { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Loader2, RefreshCw, Shield } from 'lucide-react';
import { toast } from 'sonner';
import { useStepUpApi } from '../../hooks/useStepUpApi';

const KINDS = [
  { value: '', label: 'All kinds' },
  { value: 'client', label: 'Client (org)' },
  { value: 'contractor', label: 'Contractor' },
  { value: 'portal_user', label: 'Portal user' },
];

const LIFECYCLES = [
  { value: '', label: 'All states' },
  { value: 'LEAD', label: 'LEAD' },
  { value: 'PENDING_SETUP', label: 'PENDING_SETUP' },
  { value: 'ACTIVE', label: 'ACTIVE' },
  { value: 'SUSPENDED', label: 'SUSPENDED' },
  { value: 'ARCHIVED', label: 'ARCHIVED' },
  { value: 'PURGE_ELIGIBLE', label: 'PURGE_ELIGIBLE' },
];

function errDetail(error) {
  const d = error?.response?.data?.detail;
  if (d && typeof d === 'object') {
    if (Array.isArray(d.blockers)) return d.blockers.join(', ');
    return d.message || JSON.stringify(d);
  }
  return typeof d === 'string' ? d : error?.message || 'Request failed';
}

export default function AdminIdentityLifecyclePage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [kind, setKind] = useState('');
  const [lifecycle, setLifecycle] = useState('');
  const [q, setQ] = useState('');
  const [rowBusy, setRowBusy] = useState(null);
  const stepUp = useStepUpApi();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 50, skip: 0 };
      if (kind) params.kind = kind;
      if (lifecycle) params.lifecycle = lifecycle;
      if (q.trim()) params.q = q.trim();
      const { data } = await adminAPI.listIdentities(params);
      setItems(data.items || []);
      setTotal(data.total ?? 0);
    } catch (e) {
      toast.error(errDetail(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [kind, lifecycle, q]);

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

  const run = async (key, fn) => {
    setRowBusy(key);
    try {
      await fn();
      toast.success('Updated');
      await load();
    } catch (e) {
      if (e?.message === 'step_up_cancelled') return;
      toast.error(errDetail(e));
    } finally {
      setRowBusy(null);
    }
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <Shield className="w-8 h-8 text-electric-teal" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Identity lifecycle</h1>
            <p className="text-sm text-gray-600">
              Cross-type control plane: clients, contractors, and portal users. Profiles stay in their collections; actions are audited as
              IDENTITY_* (alongside existing CLIENT_* / USER_* logs where applicable).
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Directory</CardTitle>
            <CardDescription>Filter by kind and normalised lifecycle. Search matches email, name, or id substring.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-3">
              <select
                className="border rounded-md px-3 py-2 text-sm"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                {KINDS.map((o) => (
                  <option key={o.value || 'all'} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <select
                className="border rounded-md px-3 py-2 text-sm"
                value={lifecycle}
                onChange={(e) => setLifecycle(e.target.value)}
              >
                {LIFECYCLES.map((o) => (
                  <option key={o.value || 'all'} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <input
                className="border rounded-md px-3 py-2 text-sm flex-1 min-w-[200px]"
                placeholder="Search…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">Showing {items.length} of {total} loaded (merged in-memory cap).</p>

            {loading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="overflow-x-auto border rounded-md">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40 text-left">
                      <th className="p-2">Kind</th>
                      <th className="p-2">Id</th>
                      <th className="p-2">Name</th>
                      <th className="p-2">Email</th>
                      <th className="p-2">Roles</th>
                      <th className="p-2">Lifecycle</th>
                      <th className="p-2 w-[280px]">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => {
                      const id = `${row.kind}:${row.id}`;
                      const busy = rowBusy === id;
                      return (
                        <tr key={id} className="border-b last:border-0">
                          <td className="p-2 font-mono text-xs">{row.kind}</td>
                          <td className="p-2 font-mono text-xs break-all max-w-[140px]">{row.id}</td>
                          <td className="p-2">{row.name}</td>
                          <td className="p-2 break-all max-w-[180px]">{row.email || '—'}</td>
                          <td className="p-2 text-xs">{(row.roles || []).join(', ')}</td>
                          <td className="p-2 text-xs font-medium">{row.lifecycle_status}</td>
                          <td className="p-2">
                            <div className="flex flex-wrap gap-1">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={busy}
                                onClick={() =>
                                  run(id, () =>
                                    stepUp.request((h) => adminAPI.identityArchive(row.kind, row.id, { archive_reason: 'admin_identity_ui' }, { headers: h }))
                                  )
                                }
                              >
                                Archive
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={busy}
                                onClick={() =>
                                  run(id, () => stepUp.request((h) => adminAPI.identityRestore(row.kind, row.id, { headers: h })))
                                }
                              >
                                Restore
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={busy}
                                onClick={() =>
                                  run(id, () => stepUp.request((h) => adminAPI.identitySuspend(row.kind, row.id, { headers: h })))
                                }
                              >
                                Suspend
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={busy}
                                onClick={() =>
                                  run(id, () => stepUp.request((h) => adminAPI.identityResume(row.kind, row.id, { headers: h })))
                                }
                              >
                                Resume
                              </Button>
                              {row.kind === 'client' ? (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="h-7 text-xs"
                                  disabled={busy}
                                  onClick={() =>
                                    run(`${id}-purge`, () =>
                                      stepUp.request((h) => adminAPI.identityMarkPurgeEligible(row.kind, row.id, { headers: h }))
                                    )
                                  }
                                >
                                  Purge eligible
                                </Button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {!items.length ? <p className="p-4 text-center text-muted-foreground text-sm">No rows</p> : null}
              </div>
            )}
          </CardContent>
        </Card>
        {stepUp.modal}
      </div>
    </UnifiedAdminLayout>
  );
}
