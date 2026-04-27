import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from '@/utils/portalNotifications';
import { filterAndSortActionLinksForRegion, portfolioJurisdictionLabelToRegion } from '../../utils/complianceRegistryOperatorUi';

/** Mirrors ``REGISTRY_PREVIEW_COVERAGE`` in ``compliance_registry_admin_service.py`` (keep in sync). */
const PREVIEW_COVERAGE_FALLBACK = {
  decorates_only: true,
  mode: 'decorate_production_plan_rows',
  summary:
    'Preview runs the production planner, then merges drafts onto rows that planner already emitted. It does not synthesise a full post-publish plan.',
  useful_for: [
    'Metadata / copy changes surfaced as description and related display fields on existing rows.',
    'Client visibility (e.g. client_surface_visible) and classification on existing rows.',
    'Jurisdiction-scoped draft matching (display_jurisdictions / scope_key) for overrides on rows that already exist in the plan.',
    'Frequency and warning cadence hints merged onto matching existing requirement types.',
  ],
  not_yet: [
    'Brand-new requirement types or plan members that would appear only after publish (would-publish expansion).',
    'Full publish-impact simulation for net-new draft-driven rows not emitted by the current planner + catalog path.',
  ],
  sequencing_note:
    'Intended order: publish queue + audited merge into the planner/materialiser path first; an expansion-aware preview mode can follow if product/legal needs it.',
};

function PreviewCoveragePanel({ coverage }) {
  const c = coverage || PREVIEW_COVERAGE_FALLBACK;
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/90 p-4 mb-6 text-sm text-slate-900">
      <h2 className="text-sm font-semibold text-slate-800 mb-2">Preview coverage (explicit limitation)</h2>
      <p className="text-xs text-slate-700 mb-3">{c.summary}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div>
          <p className="font-medium text-slate-800 mb-1">Already useful for</p>
          <ul className="list-disc pl-4 space-y-1 text-slate-700">
            {(c.useful_for || []).map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="font-medium text-amber-900 mb-1">Not a complete publish simulator (yet)</p>
          <ul className="list-disc pl-4 space-y-1 text-amber-950/90">
            {(c.not_yet || []).map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      </div>
      <p className="text-xs text-slate-600 mt-3 border-t border-slate-200 pt-2">{c.sequencing_note}</p>
    </div>
  );
}

export default function AdminComplianceRegistryPreviewPage() {
  const { isOwner, isAdmin, isSupport } = useAuth();
  const canRunRequirementsSync = Boolean(isOwner?.() || isAdmin?.() || isSupport?.());
  const [propertyId, setPropertyId] = useState('');
  const [clients, setClients] = useState([]);
  const [properties, setProperties] = useState([]);
  const [selectedClientId, setSelectedClientId] = useState('');
  const [includeExplain, setIncludeExplain] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingProps, setLoadingProps] = useState(false);
  const [syncBusy, setSyncBusy] = useState(false);

  useEffect(() => {
    adminAPI
      .getClients(0, 400)
      .then((res) => setClients(res.data?.clients || res.data?.items || []))
      .catch(() => setClients([]));
  }, []);

  const loadProperties = useCallback((clientId) => {
    if (!clientId) {
      setProperties([]);
      return;
    }
    setLoadingProps(true);
    adminAPI
      .getClientDetail(clientId)
      .then((res) => {
        const props = res.data?.properties || [];
        setProperties(Array.isArray(props) ? props : []);
      })
      .catch(() => setProperties([]))
      .finally(() => setLoadingProps(false));
  }, []);

  useEffect(() => {
    loadProperties(selectedClientId);
  }, [selectedClientId, loadProperties]);

  const runPreview = () => {
    const pid = propertyId.trim();
    if (!pid) {
      toast.error('Enter or select a property_id');
      return;
    }
    setLoading(true);
    adminAPI
      .getComplianceRegistryPreviewSimulation({
        property_id: pid,
        include_explanations: includeExplain || undefined,
      })
      .then((res) => {
        setData(res.data);
        toast.success('Preview loaded');
      })
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : 'Preview failed', { critical: true });
        setData(null);
      })
      .finally(() => setLoading(false));
  };

  const runSyncFromRegistry = () => {
    const pid = propertyId.trim();
    if (!pid) {
      toast.error('Enter or select a property_id');
      return;
    }
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
  };

  const rowsWithDelta = (data?.rows || []).filter((r) => Object.keys(r.registry_preview?.deltas || {}).length > 0);
  const portfolioLabel = data?.portfolio_jurisdiction_label;
  const regionForProperty = data ? portfolioJurisdictionLabelToRegion(portfolioLabel) : 'ENGLAND';

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-7xl">
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <Link to="/admin/compliance/registry" className="text-sm text-electric-teal hover:underline">
            ← Policy Registry (drafts)
          </Link>
          <Link to="/admin/compliance/registry/publish-queue" className="text-sm text-electric-teal hover:underline">
            Publish queue
          </Link>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Preview &amp; simulation</h1>
        <p className="text-sm text-gray-600 mb-3 max-w-3xl">
          Uses the same planner as production (<code className="text-xs bg-gray-100 px-1 rounded">build_requirement_plan_for_property</code>
          + serializer), including any <strong>active published</strong> registry snapshot, then merges <strong>all</strong> Mongo
          registry drafts as further <strong>read-only overlays</strong>. No writes; does not persist preview rows.
        </p>
        <div className="rounded-lg border border-amber-200 bg-amber-50/90 p-3 mb-4 text-xs text-amber-950">
          Unpublished drafts never affect client generation. Only entries promoted through the publish queue change the live
          published overlay; this page still only <strong>decorates</strong> rows the planner already produces (see coverage
          panel).
        </div>

        <PreviewCoveragePanel coverage={data?.preview_coverage} />

        <div className="flex flex-wrap gap-4 mb-6 items-end">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Client (load properties)</label>
            <select
              value={selectedClientId}
              onChange={(e) => setSelectedClientId(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm min-w-[220px] bg-white"
            >
              <option value="">—</option>
              {clients.map((c) => (
                <option key={c.client_id} value={c.client_id}>
                  {(c.company_name || c.full_name || c.client_id) + ` (${c.client_id})`}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Property</label>
            <select
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
              disabled={loadingProps || !selectedClientId}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm min-w-[260px] bg-white"
            >
              <option value="">{loadingProps ? 'Loading…' : 'Select property'}</option>
              {properties.map((p) => (
                <option key={p.property_id} value={p.property_id}>
                  {(p.address_line1 || p.postcode || p.property_id) + ` (${p.property_id})`}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Or paste property_id</label>
            <input
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
              placeholder="property_id"
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-56 font-mono"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={includeExplain} onChange={(e) => setIncludeExplain(e.target.checked)} />
            Include explanations
          </label>
          <Button type="button" size="sm" onClick={runPreview} disabled={loading}>
            {loading ? 'Running…' : 'Run preview'}
          </Button>
        </div>

        {canRunRequirementsSync && (
          <div className="rounded-lg border border-gray-200 bg-white p-4 mb-6 text-sm">
            <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
              Per-property requirements sync
            </h2>
            <p className="text-xs text-gray-600 mb-3">
              Uses the <span className="font-mono">property_id</span> above. After you publish or revert the registry, or
              when preview shows drift you have corrected in the live snapshot, run this to update Mongo requirements for
              this property only (not fleet-wide).
            </p>
            <Button
              type="button"
              size="sm"
              disabled={syncBusy || !propertyId.trim()}
              onClick={runSyncFromRegistry}
            >
              {syncBusy ? 'Syncing…' : 'Sync from registry'}
            </Button>
          </div>
        )}

        {data && (
          <div className="space-y-4">
            <div className="text-sm text-gray-700">
              <span className="font-medium">Portfolio label:</span> {data.portfolio_jurisdiction_label} ·{' '}
              <span className="font-medium">Resolved region (links):</span> <span className="font-mono">{regionForProperty}</span>{' '}
              ·<span className="font-medium"> Drafts considered:</span> {data.draft_documents_considered} ·{' '}
              <span className="font-medium">Plan rows:</span> {data.planned_row_count} ·{' '}
              <span className="font-medium">Rows with overlay delta:</span> {rowsWithDelta.length}
            </div>
            <div className="rounded-lg border border-teal-200 bg-teal-50/90 p-4 text-sm text-teal-950">
              <h2 className="text-sm font-semibold text-teal-900 mb-1">Effective action links (this property’s region)</h2>
              <p className="text-xs text-teal-800/90 mb-3">
                Each plan row’s <span className="font-mono">action_links</span> after production merge and after preview
                overlay. Shown for <span className="font-mono">{regionForProperty}</span> (from portfolio label), sorted by{' '}
                <span className="font-mono">priority</span> — the same array fields the registry editor edits. Client
                resolvers can still add manual / static-fallback rules not shown on this plan snapshot.
              </p>
              <div className="overflow-x-auto border border-teal-100 rounded bg-white/80 max-h-56 overflow-y-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-teal-100/60 sticky top-0">
                    <tr>
                      <th className="p-2">Requirement</th>
                      <th className="p-2">Production (plan row)</th>
                      <th className="p-2">Preview (with draft merge)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.rows || [])
                      .filter(
                        (r) =>
                          (r.production?.action_links && r.production.action_links.length) ||
                          (r.preview?.action_links && r.preview.action_links.length),
                      )
                      .map((r) => {
                        const pLinks = filterAndSortActionLinksForRegion(r.production?.action_links, regionForProperty);
                        const vLinks = filterAndSortActionLinksForRegion(r.preview?.action_links, regionForProperty);
                        return (
                          <tr key={r.requirement_type} className="border-t border-teal-100">
                            <td className="p-2 font-mono align-top whitespace-nowrap">{r.requirement_type}</td>
                            <td className="p-2 align-top text-gray-800 max-w-sm">
                              {pLinks.length ? (
                                <ul className="list-disc pl-4 space-y-1">
                                  {pLinks.map((l) => (
                                    <li key={l.key || l.url}>
                                      <span className="font-medium">{l.label || l.key}</span>{' '}
                                      {l.url ? (
                                        <a
                                          className="text-electric-teal break-all"
                                          href={l.url}
                                          target="_blank"
                                          rel="noreferrer"
                                        >
                                          {l.url}
                                        </a>
                                      ) : null}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <span className="text-gray-400">—</span>
                              )}
                            </td>
                            <td className="p-2 align-top text-gray-900 max-w-sm">
                              {vLinks.length ? (
                                <ul className="list-disc pl-4 space-y-1">
                                  {vLinks.map((l) => (
                                    <li key={`${(l.key || l.url) || 'x'}v`}>
                                      <span className="font-medium">{l.label || l.key}</span>{' '}
                                      {l.url ? (
                                        <a
                                          className="text-electric-teal break-all"
                                          href={l.url}
                                          target="_blank"
                                          rel="noreferrer"
                                        >
                                          {l.url}
                                        </a>
                                      ) : null}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <span className="text-gray-400">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    {!(data.rows || []).some(
                      (r) =>
                        (r.production?.action_links && r.production.action_links.length) ||
                        (r.preview?.action_links && r.preview.action_links.length),
                    ) && (
                      <tr>
                        <td colSpan={3} className="p-3 text-gray-500">
                          No action links on plan rows in this result (or none for this run).
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="overflow-x-auto border border-gray-200 rounded-lg max-h-[70vh] overflow-y-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gray-50 sticky top-0 z-10">
                  <tr>
                    <th className="p-2">Type</th>
                    <th className="p-2">Production</th>
                    <th className="p-2">Preview (draft merge)</th>
                    <th className="p-2">Overlays</th>
                    <th className="p-2">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.rows || []).map((r) => {
                    const dkeys = Object.keys(r.registry_preview?.deltas || {});
                    return (
                      <tr key={r.requirement_type} className={dkeys.length ? 'bg-amber-50/50' : ''}>
                        <td className="p-2 font-mono whitespace-nowrap align-top">{r.requirement_type}</td>
                        <td className="p-2 align-top font-mono text-gray-700 whitespace-pre-wrap break-all max-w-[200px]">
                          {JSON.stringify(r.production, null, 0)}
                        </td>
                        <td className="p-2 align-top font-mono text-gray-900 whitespace-pre-wrap break-all max-w-[200px]">
                          {JSON.stringify(r.preview, null, 0)}
                        </td>
                        <td className="p-2 align-top text-gray-600 max-w-[180px]">
                          {(r.registry_preview?.overlay_sources || []).map((s) => (
                            <div key={s.entry_id} className="mb-1">
                              {s.canonical_code} / {s.scope_key}
                              <br />
                              <span className="text-[10px] text-gray-400">{s.entry_id}</span>
                            </div>
                          ))}
                          {!r.registry_preview?.overlay_count && '—'}
                        </td>
                        <td className="p-2 align-top text-gray-800 max-w-[220px]">
                          {dkeys.length ? JSON.stringify(r.registry_preview.deltas, null, 0) : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
