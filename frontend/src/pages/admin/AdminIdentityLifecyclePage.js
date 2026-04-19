import React, { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Loader2, RefreshCw, Shield } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import { useStepUpApi } from '../../hooks/useStepUpApi';
import { useAuth } from '../../contexts/AuthContext';
import AccountEnvironmentBadge from '../../components/admin/AccountEnvironmentBadge';
import { accountEnvironmentActionNote } from '../../utils/adminAccountClassification';

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
  { value: 'SUSPENDED', label: 'Deactivated (suspended)' },
  { value: 'ARCHIVED', label: 'ARCHIVED' },
  { value: 'PURGE_ELIGIBLE', label: 'PURGE_ELIGIBLE' },
];

const FLAGS = [
  { value: '', label: 'All records' },
  { value: 'live', label: 'Live (production) only' },
  { value: 'test_like', label: 'Test / Dummy / Pre-production only' },
];

const HARD_DELETE_CONFIRM_PHRASE = 'PERMANENTLY DELETE TEST ACCOUNT';

function errDetail(error) {
  const d = error?.response?.data?.detail;
  if (d && typeof d === 'object') {
    if (Array.isArray(d.blockers)) return d.blockers.join(', ');
    return d.message || JSON.stringify(d);
  }
  return typeof d === 'string' ? d : error?.message || 'Request failed';
}

export default function AdminIdentityLifecyclePage() {
  const { user: authUser } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [kind, setKind] = useState('');
  const [lifecycle, setLifecycle] = useState('');
  const [flags, setFlags] = useState('');
  const [q, setQ] = useState('');
  const [rowBusy, setRowBusy] = useState(null);
  const stepUp = useStepUpApi();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        limit: 50,
        skip: 0,
        include_hard_delete_eligibility: true,
      };
      if (kind) params.kind = kind;
      if (lifecycle) params.lifecycle = lifecycle;
      if (flags) params.flags = flags;
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
  }, [kind, lifecycle, flags, q]);

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

  const isOwner = authUser?.role === 'ROLE_OWNER';
  const isOwnerOrAdmin = isOwner || authUser?.role === 'ROLE_ADMIN';

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <Shield className="w-8 h-8 text-electric-teal" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Identity lifecycle</h1>
            <p className="text-sm text-gray-600">
              Archive and restore keep full history. <strong>Deactivate account</strong> removes login without hiding the
              row. <strong>Permanently delete test account</strong> is Owner-only and only when pre-flight checks pass
              (mark portal users as test/dummy first if they have audit history).
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Directory</CardTitle>
            <CardDescription>
              Filter by kind, lifecycle, or test/dummy. Search matches email, name, or id. Hard-delete eligibility is
              computed for portal users on this page.
            </CardDescription>
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
              <select
                className="border rounded-md px-3 py-2 text-sm"
                value={flags}
                onChange={(e) => setFlags(e.target.value)}
              >
                {FLAGS.map((o) => (
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
                      <th className="p-2">Status</th>
                      <th className="p-2 min-w-[320px]">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => {
                      const id = `${row.kind}:${row.id}`;
                      const busy = rowBusy === id;
                      const ls = row.lifecycle_status || '';
                      const archived = ls === 'ARCHIVED';
                      const suspended = ls === 'SUSPENDED';
                      const portal = row.kind === 'portal_user';
                      return (
                        <tr key={id} className="border-b last:border-0">
                          <td className="p-2 font-mono text-xs">{row.kind}</td>
                          <td className="p-2 font-mono text-xs break-all max-w-[140px]">{row.id}</td>
                          <td className="p-2">{row.name}</td>
                          <td className="p-2 break-all max-w-[180px]">{row.email || '—'}</td>
                          <td className="p-2 text-xs">{(row.roles || []).join(', ')}</td>
                          <td className="p-2">
                            <div className="flex flex-wrap gap-1 items-center">
                              <Badge variant="outline" className="text-xs font-normal">
                                {ls || '—'}
                              </Badge>
                              {(row.kind === 'client' || row.kind === 'portal_user') && (
                                <AccountEnvironmentBadge doc={row} showLiveBadge />
                              )}
                            </div>
                          </td>
                          <td className="p-2">
                            <div className="flex flex-wrap gap-1">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={busy || archived}
                                title={archived ? 'Already archived' : 'Hides from active lists; keeps all data'}
                                onClick={() => {
                                  if (
                                    !window.confirm(
                                      'Archive this account? Login access is removed and the account is hidden from primary lists. All history is kept.',
                                    )
                                  ) {
                                    return;
                                  }
                                  run(id, () =>
                                    stepUp.request((h) =>
                                      adminAPI.identityArchive(row.kind, row.id, { archive_reason: 'admin_identity_ui' }, { headers: h }),
                                    ),
                                  );
                                }}
                              >
                                Archive account
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={busy || !archived}
                                title={!archived ? 'Not archived' : 'Restore visibility and access where applicable'}
                                onClick={() => {
                                  if (!window.confirm('Restore this archived account?')) return;
                                  run(id, () => stepUp.request((h) => adminAPI.identityRestore(row.kind, row.id, { headers: h })));
                                }}
                              >
                                Restore account
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={busy || archived || suspended}
                                title="Removes login access; record stays visible (not archived)"
                                onClick={() => {
                                  if (
                                    !window.confirm(
                                      'Deactivate this account? The user cannot sign in until you resume. Data is not removed.',
                                    )
                                  ) {
                                    return;
                                  }
                                  run(id, () => stepUp.request((h) => adminAPI.identitySuspend(row.kind, row.id, { headers: h })));
                                }}
                              >
                                Deactivate account
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={busy || !suspended || archived}
                                title="Re-enable login after deactivation"
                                onClick={() => {
                                  if (!window.confirm('Resume this account and allow login again?')) return;
                                  run(id, () => stepUp.request((h) => adminAPI.identityResume(row.kind, row.id, { headers: h })));
                                }}
                              >
                                Resume account
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
                                      stepUp.request((h) => adminAPI.identityMarkPurgeEligible(row.kind, row.id, { headers: h })),
                                    )
                                  }
                                >
                                  Purge eligible
                                </Button>
                              ) : null}
                              {portal && isOwnerOrAdmin ? (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="secondary"
                                  className="h-7 text-xs"
                                  disabled={busy}
                                  title="Needed so test accounts with audit history can pass hard-delete preflight"
                                  onClick={() =>
                                    run(`${id}-test`, () =>
                                      stepUp.request((h) =>
                                        adminAPI.identitySetTestLike(row.kind, row.id, { is_test_like: !row.is_test_like }, { headers: h }),
                                      ),
                                    )
                                  }
                                >
                                  {row.is_test_like ? 'Clear test flag' : 'Mark test / dummy'}
                                </Button>
                              ) : null}
                              {portal && isOwner && archived ? (
                                row.hard_delete_allowed ? (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="destructive"
                                    className="h-7 text-xs"
                                    disabled={busy}
                                    onClick={() => {
                                      const envNote = accountEnvironmentActionNote(Boolean(row.is_test_like));
                                      if (
                                        !window.confirm(
                                          `${envNote}\n\nThis permanently deletes this portal user row when policy allows. Billing and client organisations are not removed. Continue?`,
                                        )
                                      ) {
                                        return;
                                      }
                                      const typed = window.prompt(
                                        `Type exactly to confirm:\n${HARD_DELETE_CONFIRM_PHRASE}`,
                                      );
                                      if (typed !== HARD_DELETE_CONFIRM_PHRASE) {
                                        toast.error('Phrase did not match — cancelled.');
                                        return;
                                      }
                                      run(`${id}-del`, () =>
                                        stepUp.request((h) => adminAPI.identityPermanentDelete(row.kind, row.id, { headers: h })),
                                      );
                                    }}
                                  >
                                    Permanently delete test account
                                  </Button>
                                ) : (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    className="h-7 text-xs"
                                    disabled
                                    title={
                                      row.hard_delete_blockers?.length
                                        ? `Not eligible: ${row.hard_delete_blockers.join(', ')}`
                                        : 'Not eligible for permanent delete'
                                    }
                                  >
                                    Delete blocked
                                  </Button>
                                )
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
