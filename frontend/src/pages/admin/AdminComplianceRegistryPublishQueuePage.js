import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from '@/utils/portalNotifications';

export default function AdminComplianceRegistryPublishQueuePage() {
  const { isOwner, isAdmin, isSupport } = useAuth();
  const canMutate = Boolean(isOwner?.() || isAdmin?.());
  const canRunRequirementsSync = Boolean(isOwner?.() || isAdmin?.() || isSupport?.());
  const isPortalOwner = Boolean(isOwner?.());
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [publishedMeta, setPublishedMeta] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [title, setTitle] = useState('');
  const [idsText, setIdsText] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [revertBusyLine, setRevertBusyLine] = useState(null);
  const [syncPropertyId, setSyncPropertyId] = useState('');
  const [syncBusy, setSyncBusy] = useState(false);
  const [publishImpactByQueue, setPublishImpactByQueue] = useState({});

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      adminAPI.listComplianceRegistryPublishQueue().catch(() => ({ data: {} })),
      adminAPI.getComplianceRegistryPublishedActive().catch(() => ({ data: {} })),
      adminAPI.listComplianceRegistryPublishedHistory({ limit: 100 }).catch(() => ({ data: {} })),
    ])
      .then(([q, p, h]) => {
        setItems(q.data?.items || []);
        setPublishedMeta(p.data || null);
        setHistoryItems(h.data?.items || []);
      })
      .catch((err) => {
        toast.error(err?.response?.data?.detail || 'Failed to load publish queue', { critical: true });
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!items.length) {
      setPublishImpactByQueue({});
      return undefined;
    }
    let cancelled = false;
    (async () => {
      const m = {};
      for (const row of items) {
        const ids = row.draft_entry_ids;
        if (!Array.isArray(ids) || !ids.length) continue;
        const csv = ids.join(',');
        try {
          // eslint-disable-next-line no-await-in-loop
          const res = await adminAPI.getComplianceRegistryPublishImpact(csv);
          if (!cancelled) m[row.queue_id] = res.data;
        } catch {
          if (!cancelled) m[row.queue_id] = null;
        }
      }
      if (!cancelled) setPublishImpactByQueue(m);
    })();
    return () => {
      cancelled = true;
    };
  }, [items]);

  const parseIds = () =>
    idsText
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);

  const createQueue = () => {
    if (!canMutate) return;
    const draft_entry_ids = parseIds();
    if (!draft_entry_ids.length) {
      toast.error('Enter at least one draft entry_id (comma or space separated).');
      return;
    }
    adminAPI
      .createComplianceRegistryPublishQueue({ title: title.trim(), draft_entry_ids })
      .then(() => {
        toast.success('Publish queue item created.');
        setIdsText('');
        setTitle('');
        refresh();
      })
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : 'Create failed', { critical: true });
      });
  };

  const runTransition = (queueId, fn, label) => {
    if (!canMutate) return;
    setBusyId(queueId);
    fn(queueId)
      .then(() => {
        const hint =
          label === 'Published'
            ? ' Active registry line updated for merged planner and resolver. Existing property rows stay as-is until per-property sync; new visits may already see copy/links from the new line where materialised. Use sync below for a specific site.'
            : '';
        toast.success(`${label}${hint ? `. ${hint}` : ''}`);
        refresh();
      })
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : `${label} failed`);
      })
      .finally(() => setBusyId(null));
  };

  const reject = (queueId) => {
    const reason = window.prompt('Rejection reason (optional)') || '';
    if (!canMutate) return;
    setBusyId(queueId);
    adminAPI
      .rejectComplianceRegistryPublishQueue(queueId, { reason })
      .then(() => {
        toast.success('Rejected');
        refresh();
      })
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : 'Reject failed', { critical: true });
      })
      .finally(() => setBusyId(null));
  };

  const revertToLineVersion = (publishedLineVersion) => {
    if (!isPortalOwner) return;
    const cur = publishedMeta?.version;
    if (cur != null && Number(publishedLineVersion) === Number(cur)) {
      toast.error('That line version is already the active singleton counter (no-op).');
      return;
    }
    if (
      !window.confirm(
        `Revert the active published snapshot to the entries from historical line version ${publishedLineVersion}? ` +
          `This increments the live version counter and does not automatically re-materialise all properties.`,
      )
    ) {
      return;
    }
    setRevertBusyLine(publishedLineVersion);
    adminAPI
      .revertComplianceRegistryPublishedToVersion(publishedLineVersion)
      .then(() => {
        toast.success(
          'Revert applied. New activation recorded in append-only history. Re-materialise per property below where needed.',
        );
        refresh();
      })
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : 'Revert failed', { critical: true });
      })
      .finally(() => setRevertBusyLine(null));
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-5xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Registry publish queue</h1>
        <p className="text-sm text-gray-600 mb-6">
          Audited workflow (draft → submitted → approved → published). <strong>Global line:</strong> the published snapshot
          is merged for planner, preview, and resolver layers immediately. <strong>Per-property data:</strong> materialised
          Mongo requirement rows for existing homes are <strong>not</strong> bulk-rewritten — use sync with a
          <span className="font-mono"> property_id</span> when a site must pick up changed rows. <strong>Approve</strong>{' '}
          and <strong>Publish</strong> are <strong>Owner-only</strong> for now; other transitions remain to Admin where shown.
        </p>
        <div className="flex flex-wrap gap-3 mb-6 text-sm">
          <Link to="/admin/compliance/registry" className="text-electric-teal hover:underline">
            ← Drafts
          </Link>
          <Link to="/admin/compliance/registry/preview" className="text-electric-teal hover:underline">
            Preview &amp; simulation
          </Link>
        </div>

        <div className="rounded-lg border border-gray-200 bg-gray-50/80 p-4 mb-6 text-sm">
          <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Active published snapshot</h2>
          {publishedMeta?.active ? (
            <p className="text-gray-800">
              Version <span className="font-mono">{publishedMeta.version}</span> —{' '}
              <span className="font-mono">{publishedMeta.entry_count}</span> entries — updated{' '}
              {publishedMeta.updated_at || '—'}
              {publishedMeta.last_queue_id && (
                <>
                  {' '}
                  (queue <span className="font-mono">{publishedMeta.last_queue_id}</span>)
                </>
              )}
            </p>
          ) : (
            <p className="text-gray-600">No active published snapshot yet. Publish an approved queue item to activate.</p>
          )}
          {publishedMeta?.rematerialisation?.detail && (
            <p className="text-xs text-gray-600 mt-3 border-t border-gray-200 pt-2">
              <strong>Rematerialisation:</strong> {publishedMeta.rematerialisation.detail}
            </p>
          )}
        </div>

        {canRunRequirementsSync && (
          <div className="rounded-lg border border-gray-200 bg-white p-4 mb-6 text-sm">
            <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
              Convergence: per-property requirements sync
            </h2>
            <p className="text-xs text-gray-600 mb-3">
              The live registry line applies globally to <em>new</em> plan materialisation, but <strong>stored</strong> rows
              for a property update only when you run sync. After publish or revert, run for each <span className="font-mono">property_id</span>{' '}
              that should reflect the new definitions — no automatic fleet run.
            </p>
            <div className="flex flex-wrap gap-2 items-end">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-medium text-gray-500 mb-1">property_id</label>
                <input
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full font-mono"
                  value={syncPropertyId}
                  onChange={(e) => setSyncPropertyId(e.target.value.trim())}
                  placeholder="e.g. prop_abc123"
                  disabled={syncBusy}
                />
              </div>
              <Button
                type="button"
                size="sm"
                disabled={syncBusy || !syncPropertyId}
                onClick={() => {
                  const pid = syncPropertyId.trim();
                  if (!pid) return;
                  setSyncBusy(true);
                  adminAPI
                    .syncPropertyRequirementsFromRegistry(pid)
                    .then((res) => {
                      const n = (res.data?.planned_types || []).length;
                      toast.success(
                        n
                          ? `Synced ${pid}: ${n} planned type(s); compliance recalculation queued.`
                          : `Synced ${pid}; compliance recalculation queued.`,
                      );
                    })
                    .catch((err) => {
                      const d = err?.response?.data?.detail;
                      toast.error(typeof d === 'string' ? d : 'Sync failed', { critical: true });
                    })
                    .finally(() => setSyncBusy(false));
                }}
              >
                {syncBusy ? 'Syncing…' : 'Sync from registry'}
              </Button>
            </div>
          </div>
        )}

        {!loading && (
          <div className="mb-6 border border-gray-200 rounded-lg overflow-x-auto">
            <div className="bg-gray-50 px-3 py-2 border-b border-gray-200">
              <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Published snapshot history</h2>
              <p className="text-xs text-gray-500 mt-1">
                Append-only activations (queue publish or Owner revert). Inspect via API with{' '}
                <code className="text-[10px] bg-gray-100 px-1 rounded">include_entries=true</code> when you need the full
                entries payload.
              </p>
            </div>
            <table className="w-full text-sm text-left">
              <thead className="text-gray-600">
                <tr>
                  <th className="p-2">Line</th>
                  <th className="p-2">Kind</th>
                  <th className="p-2">Entries</th>
                  <th className="p-2">Recorded</th>
                  <th className="p-2">Queue</th>
                  <th className="p-2 w-40">Actions</th>
                </tr>
              </thead>
              <tbody>
                {historyItems.map((row) => {
                  const lv = row.published_line_version;
                  const isCurrentCounter = publishedMeta?.active && Number(lv) === Number(publishedMeta?.version);
                  return (
                    <tr key={row.history_id || lv} className="border-t border-gray-100">
                      <td className="p-2 font-mono">{lv}</td>
                      <td className="p-2 whitespace-nowrap">{row.activation_kind || '—'}</td>
                      <td className="p-2 font-mono">{row.entry_count ?? '—'}</td>
                      <td className="p-2 text-xs text-gray-600 whitespace-nowrap">{row.recorded_at || '—'}</td>
                      <td className="p-2 font-mono text-xs break-all max-w-[140px]">{row.last_queue_id || '—'}</td>
                      <td className="p-2">
                        {isPortalOwner && !isCurrentCounter && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={revertBusyLine != null}
                            onClick={() => revertToLineVersion(lv)}
                          >
                            {revertBusyLine === lv ? 'Reverting…' : 'Revert to this'}
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!historyItems.length && <p className="p-3 text-gray-500 text-sm">No history rows yet (publish once to seed).</p>}
          </div>
        )}

        {canMutate && (
          <div className="border border-gray-200 rounded-lg p-4 mb-6 space-y-3">
            <h2 className="text-sm font-semibold text-gray-800">New queue item</h2>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Title</label>
              <input
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full max-w-md"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Q2 cadence alignment"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Draft entry IDs</label>
              <textarea
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full font-mono min-h-[72px]"
                value={idsText}
                onChange={(e) => setIdsText(e.target.value)}
                placeholder="Paste entry_id values (UUIDs), comma or newline separated"
              />
            </div>
            <Button type="button" size="sm" onClick={createQueue}>
              Create draft queue item
            </Button>
          </div>
        )}

        {loading ? (
          <p className="text-gray-500 text-sm">Loading…</p>
        ) : (
          <div className="overflow-x-auto border border-gray-200 rounded-lg">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="p-3">Queue ID</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Title</th>
                  <th className="p-3">Drafts</th>
                  <th className="p-3 min-w-[220px]">Impact (pre-publish)</th>
                  <th className="p-3 w-48">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const st = row.status || '';
                  const qid = row.queue_id;
                  const disabled = busyId === qid;
                  const imp = publishImpactByQueue[qid];
                  const im = imp?.impact;
                  return (
                    <tr key={qid} className="border-t border-gray-100">
                      <td className="p-3 font-mono text-xs align-top break-all max-w-[200px]">{qid}</td>
                      <td className="p-3 align-top whitespace-nowrap">{st}</td>
                      <td className="p-3 align-top">{row.title || '—'}</td>
                      <td className="p-3 align-top text-xs text-gray-600">{(row.draft_entry_ids || []).length}</td>
                      <td className="p-3 align-top text-xs text-gray-700 max-w-sm">
                        {!imp && <span className="text-gray-400">…</span>}
                        {im && (
                          <div className="space-y-0.5">
                            <p>
                              <span className="font-medium">{im.draft_count}</span> line(s) · changes{' '}
                              <span className="font-mono">
                                {im.per_draft?.filter((d) => d.change_kind === 'new').length || 0} new,{' '}
                                {im.per_draft?.filter((d) => d.change_kind === 'update').length || 0} update
                              </span>
                            </p>
                            <p className="text-gray-600">Regions in union: { (im.display_regions_union || []).join(', ') || '—'}</p>
                            {im.broad_uk_operator_warning && (
                              <p className="text-amber-800 font-medium">Includes a rule covering all four UK display regions—confirm.</p>
                            )}
                            {im.has_blocking_validation_errors && (
                              <p className="text-red-700 font-medium">Validation blockers on one or more drafts — cannot publish until fixed in editor.</p>
                            )}
                            <p className="text-gray-500">{imp?.rematerialisation?.detail}</p>
                          </div>
                        )}
                      </td>
                      <td className="p-3 align-top space-x-1 flex flex-wrap gap-1">
                        {canMutate && st === 'draft' && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={disabled}
                            onClick={() =>
                              runTransition(qid, adminAPI.submitComplianceRegistryPublishQueue, 'Submitted')
                            }
                          >
                            Submit
                          </Button>
                        )}
                        {canMutate && st === 'submitted' && (
                          <>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={disabled}
                              onClick={() =>
                                runTransition(qid, adminAPI.approveComplianceRegistryPublishQueue, 'Approved')
                              }
                            >
                              Approve
                            </Button>
                            <Button type="button" variant="destructive" size="sm" disabled={disabled} onClick={() => reject(qid)}>
                              Reject
                            </Button>
                          </>
                        )}
                        {canMutate && st === 'approved' && (
                          <>
                            <Button
                              type="button"
                              size="sm"
                              disabled={disabled}
                              onClick={() =>
                                runTransition(qid, adminAPI.publishComplianceRegistryPublishQueue, 'Published')
                              }
                            >
                              Publish
                            </Button>
                            <Button type="button" variant="destructive" size="sm" disabled={disabled} onClick={() => reject(qid)}>
                              Reject
                            </Button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!items.length && <p className="p-4 text-gray-500 text-sm">No queue items yet.</p>}
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
