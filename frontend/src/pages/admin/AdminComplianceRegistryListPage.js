import React, { useEffect, useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from 'sonner';
import {
  formatDisplayJurisdictions,
  formatScopeKeyLabel,
  formatReviewFieldLabel,
  registryListRowState,
  publishedLineStatusForRow,
} from '../../utils/complianceRegistryOperatorUi';

function TriageBlock({ title, items }) {
  const list = Array.isArray(items) ? items : items == null ? [] : [String(items)];
  return (
    <div className="border border-amber-100 rounded-lg p-3 bg-amber-50/60">
      <h3 className="text-xs font-semibold text-amber-900 uppercase tracking-wide mb-2">{title}</h3>
      {list.length === 0 ? (
        <p className="text-xs text-amber-800/80">None recorded in this bundle. Re-check after the next import revision.</p>
      ) : (
        <ul className="text-xs text-amber-950 space-y-1.5 list-disc pl-4">
          {list.map((row, i) => (
            <li key={i}>{typeof row === 'string' ? row : JSON.stringify(row)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EditableStatusBadge({ intent, label }) {
  const c =
    intent === 'review'
      ? 'bg-amber-100 text-amber-900 border-amber-200'
      : 'bg-teal-50 text-teal-900 border-teal-200';
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded font-semibold border ${c} whitespace-nowrap`}>{label}</span>
  );
}

export default function AdminComplianceRegistryListPage() {
  const navigate = useNavigate();
  const { isOwner, isAdmin } = useAuth();
  const canMutate = Boolean(isOwner?.() || isAdmin?.());
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [reviewQueueTotal, setReviewQueueTotal] = useState(0);
  const [qInput, setQInput] = useState('');
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [meta, setMeta] = useState(null);
  const [importing, setImporting] = useState(false);
  const [liveKeys, setLiveKeys] = useState(null);

  const fetchList = useCallback(
    (search) => {
      setLoading(true);
      const qq = (search || '').trim();
      adminAPI
        .listComplianceRegistryDrafts({
          q: qq || undefined,
          limit: 200,
          needs_review: needsReviewOnly || undefined,
        })
        .then((res) => {
          setItems(res.data?.items || []);
          setTotal(res.data?.total ?? 0);
          setReviewQueueTotal(res.data?.review_queue_total ?? 0);
        })
        .catch((err) => {
          toast.error(err?.response?.data?.detail || 'Failed to load registry drafts');
          setItems([]);
        })
        .finally(() => setLoading(false));
    },
    [needsReviewOnly],
  );

  useEffect(() => {
    fetchList(qInput);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchList]);

  useEffect(() => {
    adminAPI
      .getComplianceRegistryBaselineBundleMeta()
      .then((res) => setMeta(res.data))
      .catch(() => setMeta(null));
  }, []);

  useEffect(() => {
    adminAPI
      .getComplianceRegistryPublishedEntryKeys()
      .then((res) => {
        const k = res.data?.keys;
        if (Array.isArray(k)) setLiveKeys(new Set(k));
        else setLiveKeys(new Set());
      })
      .catch(() => setLiveKeys(new Set()));
  }, [items.length, importing]);

  const runImport = (force) => {
    if (!canMutate) return;
    setImporting(true);
    adminAPI
      .importComplianceRegistryBaselineBundle({ force })
      .then((res) => {
        const s = res.data?.summary || {};
        const br = res.data?.baseline_manual_review || {};
        const triageCounts = [
          Array.isArray(br.unmapped_workbook_rows) ? br.unmapped_workbook_rows.length : 0,
          Array.isArray(br.detected_conflicts) ? br.detected_conflicts.length : 0,
          Array.isArray(br.suspected_cross_jurisdiction_mixing) ? br.suspected_cross_jurisdiction_mixing.length : 0,
        ].reduce((a, b) => a + b, 0);
        const ins = s.inserted ?? 0;
        const upd = s.updated ?? 0;
        const sk = s.skipped_existing ?? 0;
        const vf = s.validation_failures;
        const vfCount = Array.isArray(vf) ? vf.length : 0;
        const firstErr = vfCount > 0 && Array.isArray(vf[0]?.errors) ? String(vf[0].errors[0] || '') : '';
        if (vfCount > 0 && ins + upd + sk === 0) {
          toast.error(
            `Import did not save any drafts: ${vfCount} validation error(s). ${firstErr ? `Example: ${firstErr}` : 'Open Network → import-baseline-bundle response for details.'}`,
          );
        } else if (vfCount > 0) {
          toast.warning(
            `Import: inserted ${ins}, updated ${upd}, skipped ${sk}. ${vfCount} row(s) failed validation. ${firstErr ? `Example: ${firstErr}` : ''}`.trim(),
          );
        } else {
          toast.success(
            `Import: inserted ${ins}, updated ${upd}, skipped ${sk}. ` +
              `Baseline triage lines on disk: ${triageCounts} (review panels below).`,
          );
        }
        fetchList(qInput);
      })
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : d?.message || 'Import failed');
      })
      .finally(() => setImporting(false));
  };

  const createDraft = () => {
    if (!canMutate) return;
    const code = window.prompt('Canonical code (e.g. GAS_SAFETY)', 'GAS_SAFETY');
    if (!code || !code.trim()) return;
    const scope = window.prompt('Scope key (DEFAULT, WALES, SCOTLAND, …)', 'DEFAULT') || 'DEFAULT';
    adminAPI
      .createComplianceRegistryDraft({ canonical_code: code.trim(), scope_key: scope.trim() })
      .then((res) => {
        toast.success('Draft created');
        window.location.href = `/admin/compliance/registry/${encodeURIComponent(res.data.entry_id)}`;
      })
      .catch((err) => {
        const d = err?.response?.data?.detail;
        if (d?.entry_id) {
          toast.error('Draft already exists for this code and scope');
          window.location.href = `/admin/compliance/registry/${encodeURIComponent(d.entry_id)}`;
        } else {
          toast.error(typeof d === 'string' ? d : JSON.stringify(d || err.message));
        }
      });
  };

  const needsReviewFields = (row) =>
    Array.isArray(row.governance?.needs_review_fields) ? row.governance.needs_review_fields : [];

  const goEdit = (entryId, e) => {
    if (e?.target?.closest('a,button')) return;
    if (!entryId) return;
    navigate(`/admin/compliance/registry/${encodeURIComponent(entryId)}`);
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Requirement Registry</h1>
        <p className="text-sm font-medium text-gray-700 mb-3">Governed compliance definition — draft / review / publish to live registry snapshot</p>

        <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-4 mb-4 text-sm text-amber-950">
          <p className="mb-2">
            <strong>Single place for governed definitions</strong> (name, copy, action links, jurisdictions). The in-code
            engine still ships defaults; the <strong>active published registry snapshot</strong> overlays onto planner output
            after publish. Baseline <strong>import is not a completeness guarantee</strong>—use the triage panels and manual
            drafts to close gaps. This is not a duplicate of legacy “requirement rules” control surfaces elsewhere.
          </p>
          <p className="text-xs text-amber-900/90">
            Use <strong>Preview &amp; simulation</strong> for read-only behaviour checks. <strong>Publish queue</strong>{' '}
            activates changes globally for resolver-backed surfaces. <strong>Per-property Mongo rows</strong> may still
            need sync after a publish — that is a separate, deliberate step (see Publish page).
          </p>
        </div>

        {meta?.mapping_summary && (
          <div className="mb-4 rounded-lg border border-gray-200 bg-white p-3">
            <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">Mapping summary (on-disk bundle)</h2>
            <p className="text-xs text-gray-800 whitespace-pre-wrap">{meta.mapping_summary}</p>
          </div>
        )}

        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-2">Manual review before treating an import as complete</h2>
          <p className="text-xs text-gray-600 mb-3">
            The on-disk JSON carries triage flags; empty lists do not mean “clean”, only that nothing was flagged in
            that category for this bundle revision. Legal/ops should still sign off.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <TriageBlock title="Unmapped workbook rows" items={meta?.unmapped_workbook_rows} />
            <TriageBlock title="Detected conflicts" items={meta?.detected_conflicts} />
            <TriageBlock title="Suspected cross-jurisdiction mixing" items={meta?.suspected_cross_jurisdiction_mixing} />
          </div>
          {meta?.disclaimer && (
            <p className="text-xs text-gray-500 mt-3 border-t border-gray-100 pt-2">{meta.disclaimer}</p>
          )}
          {meta && (
            <p className="text-xs text-gray-400 mt-1">
              Bundle: {meta.import_bundle_version || '—'} · {meta.entry_count ?? 0} entries
              {meta.source ? ` · source: ${meta.source}` : ''}
            </p>
          )}
        </div>

        <div className="flex flex-wrap gap-3 mb-4 items-end">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Search</label>
            <input
              value={qInput}
              onChange={(e) => setQInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchList(qInput)}
              placeholder="Code or name"
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-56"
            />
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => fetchList(qInput)} disabled={loading}>
            Search
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => { setQInput(''); fetchList(''); }} disabled={loading}>
            Clear &amp; refresh
          </Button>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={needsReviewOnly}
              onChange={(e) => setNeedsReviewOnly(e.target.checked)}
            />
            Show review queue only
            <span className="text-xs text-gray-500">({reviewQueueTotal} with flags)</span>
          </label>
          {canMutate && (
            <>
              <Button type="button" size="sm" onClick={() => runImport(false)} disabled={importing}>
                Import baseline (skip existing)
              </Button>
              <Button type="button" variant="destructive" size="sm" onClick={() => runImport(true)} disabled={importing}>
                Re-import baseline (force)
              </Button>
              <div className="flex flex-col items-start">
                <Button type="button" size="sm" onClick={createDraft} className="w-full sm:w-auto">
                  New manual draft
                </Button>
                <span className="text-[10px] text-gray-500 max-w-xs mt-0.5">Adds a blank governed row for a code+scope, same review path as imported rows.</span>
              </div>
            </>
          )}
          <Link to="/admin/compliance/registry/preview" className="text-sm text-electric-teal hover:underline self-center">
            Preview &amp; simulation
          </Link>
          <Link to="/admin/compliance/registry/publish-queue" className="text-sm text-electric-teal hover:underline self-center">
            Publish queue
          </Link>
          <Link to="/admin/ops/compliance" className="text-sm text-gray-600 hover:underline self-center ml-auto" title="Live portfolio KMI; not a registry editor">
            Ops compliance snapshot
          </Link>
        </div>

        <p className="text-xs text-gray-500 mb-2">
          {needsReviewOnly ? `Review queue: ${total} shown` : `Showing ${items.length} of ${total} draft line(s)`}
          {!needsReviewOnly && reviewQueueTotal > 0 && (
            <span className="text-amber-800"> — {reviewQueueTotal} need editorial review (flags below)</span>
          )}
        </p>

        {loading ? (
          <p className="text-gray-500 text-sm">Loading…</p>
        ) : (
          <div className="overflow-x-auto border border-gray-200 rounded-lg">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="p-3">Name</th>
                  <th className="p-3">Code</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Live snapshot</th>
                  <th className="p-3">Scope</th>
                  <th className="p-3">Review focus</th>
                  <th className="p-3">Jurisdictions (display)</th>
                  <th className="p-3 w-32"> </th>
                  <th className="p-3">Updated</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const nrf = needsReviewFields(row);
                  const st = registryListRowState(row);
                  const pub = publishedLineStatusForRow(liveKeys, row.canonical_code, row.scope_key);
                  return (
                    <tr
                      key={row.entry_id}
                      onClick={(e) => goEdit(row.entry_id, e)}
                      className="border-t border-gray-100 hover:bg-teal-50/50 cursor-pointer"
                    >
                      <td className="p-3 align-top font-medium text-midnight-blue min-w-[160px]">
                        {row.identity?.name || '—'}
                        <div className="text-[10px] text-gray-400 font-normal">Click row to edit in registry editor</div>
                      </td>
                      <td className="p-3 font-mono text-xs text-gray-700 align-top whitespace-nowrap">{row.canonical_code}</td>
                      <td className="p-3 align-top">
                        <EditableStatusBadge intent={st.intent} label={st.label} />
                        {nrf.length > 0 && st.intent !== 'review' ? (
                          <div className="text-[9px] text-amber-800 mt-0.5">(also has flags)</div>
                        ) : null}
                      </td>
                      <td className="p-3 align-top text-xs">
                        {pub === 'in_snapshot' ? (
                          <span className="text-green-800 bg-green-50 border border-green-100 rounded px-1.5 py-0.5 font-medium">
                            In live snapshot
                          </span>
                        ) : liveKeys && liveKeys.size > 0 ? (
                          <span className="text-gray-500">Not in current snapshot</span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="p-3 align-top text-gray-800 text-sm">{formatScopeKeyLabel(row.scope_key)}</td>
                      <td className="p-3 align-top max-w-[240px]">
                        {nrf.length ? (
                          <div className="flex flex-wrap gap-1">
                            {nrf.map((t) => (
                              <span
                                key={t}
                                className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 font-medium"
                                title={t}
                              >
                                {formatReviewFieldLabel(t)}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">—</span>
                        )}
                      </td>
                      <td className="p-3 text-gray-700 text-xs align-top min-w-[140px]">
                        {formatDisplayJurisdictions(row.jurisdiction?.display_jurisdictions || [])}
                      </td>
                      <td className="p-3 align-top">
                        <Button
                          type="button"
                          size="sm"
                          variant="default"
                          className="h-8 text-xs w-full"
                          onClick={() => navigate(`/admin/compliance/registry/${encodeURIComponent(row.entry_id)}`)}
                        >
                          Open editor
                        </Button>
                        <p className="text-[9px] text-center text-gray-500 mt-1">or click row</p>
                      </td>
                      <td className="p-3 text-gray-500 text-xs align-top whitespace-nowrap">{row.updated_at || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!items.length && (
              <div className="p-4 text-sm text-gray-600 border-t border-gray-100">
                {needsReviewOnly ? (
                  <p>No drafts are currently flagged in the review queue (or filters exclude them).</p>
                ) : (
                  <>
                    <p className="font-medium text-gray-800 mb-1">No draft registry lines yet</p>
                    <p>
                      <strong>Your live tenant requirements are not empty because of this table.</strong> The operational
                      catalogue and planner still apply from product code. An empty list here only means: no draft rows
                      have been <strong>imported</strong> or <strong>manually created</strong> in this governed workspace
                      yet. Use <strong>Import baseline</strong> or <strong>New manual draft</strong> to start.
                    </p>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
