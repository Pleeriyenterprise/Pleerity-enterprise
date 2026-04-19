import React, { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { toast } from '@/utils/portalNotifications';

function JsonBlock({ title, data }) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-3 py-2 text-xs font-medium text-gray-600">{title}</div>
      <pre className="p-3 text-xs overflow-auto max-h-64 bg-white text-gray-800">{JSON.stringify(data ?? null, null, 2)}</pre>
    </div>
  );
}

function LinksTable({ title, rows }) {
  const list = Array.isArray(rows) ? rows : [];
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-3 py-2 text-xs font-medium text-gray-600">{title}</div>
      {list.length === 0 ? (
        <p className="p-3 text-sm text-gray-500">None</p>
      ) : (
        <table className="w-full text-xs">
          <thead className="bg-white border-b border-gray-100 text-gray-500">
            <tr>
              <th className="text-left p-2">key</th>
              <th className="text-left p-2">label</th>
              <th className="text-left p-2">url</th>
              <th className="text-left p-2">jurisdictions</th>
              <th className="text-left p-2">active</th>
              <th className="text-right p-2">priority</th>
            </tr>
          </thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.key || r.url} className="border-t border-gray-50">
                <td className="p-2 font-mono">{r.key}</td>
                <td className="p-2">{r.label}</td>
                <td className="p-2 break-all max-w-[200px]">{r.url}</td>
                <td className="p-2">{(r.jurisdictions || []).join(', ')}</td>
                <td className="p-2">{r.is_active === false ? 'no' : 'yes'}</td>
                <td className="p-2 text-right tabular-nums">{r.priority}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function AdminOpsActionLinksPage() {
  const [propertyId, setPropertyId] = useState('');
  const [requirementId, setRequirementId] = useState('');
  const [reqItems, setReqItems] = useState([]);
  const [preview, setPreview] = useState(null);
  const [draftJson, setDraftJson] = useState('[]');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadRequirementsLite = useCallback(async () => {
    const pid = propertyId.trim();
    if (!pid) {
      toast.error('Enter a property_id first');
      return;
    }
    setLoading(true);
    try {
      const { data } = await adminAPI.getPropertyRequirementsLite(pid);
      setReqItems(data.items || []);
      if (!requirementId && (data.items || []).length === 1) {
        setRequirementId(String(data.items[0].requirement_id || ''));
      }
      toast.success(`Loaded ${(data.items || []).length} requirement row(s)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load requirements', { critical: true });
      setReqItems([]);
    } finally {
      setLoading(false);
    }
  }, [propertyId, requirementId]);

  const loadPreview = useCallback(async () => {
    const pid = propertyId.trim();
    const rid = requirementId.trim();
    if (!pid || !rid) {
      toast.error('property_id and requirement_id are required');
      return;
    }
    setLoading(true);
    try {
      const { data } = await adminAPI.getRequirementActionLinksPreview(pid, rid);
      setPreview(data);
      const seed = data.override_draft ?? data.override_published ?? [];
      setDraftJson(JSON.stringify(seed, null, 2));
      toast.success('Preview loaded');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load preview', { critical: true });
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, [propertyId, requirementId]);

  const saveDraft = async () => {
    let links;
    try {
      links = JSON.parse(draftJson || '[]');
    } catch {
      toast.error('Draft JSON is invalid');
      return;
    }
    if (!Array.isArray(links)) {
      toast.error('Draft must be a JSON array');
      return;
    }
    const pid = propertyId.trim();
    const rid = requirementId.trim();
    if (!pid || !rid) return;
    setBusy(true);
    try {
      await adminAPI.putRequirementActionLinksDraft(pid, rid, { links });
      toast.success('Draft saved');
      await loadPreview();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === 'object' ? JSON.stringify(d) : d || 'Save failed', { critical: true });
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    const pid = propertyId.trim();
    const rid = requirementId.trim();
    if (!pid || !rid) return;
    setBusy(true);
    try {
      await adminAPI.publishRequirementActionLinks(pid, rid);
      toast.success('Published — portal uses override on next load');
      await loadPreview();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === 'object' ? JSON.stringify(d) : d || 'Publish failed');
    } finally {
      setBusy(false);
    }
  };

  const revert = async () => {
    const pid = propertyId.trim();
    const rid = requirementId.trim();
    if (!pid || !rid) return;
    setBusy(true);
    try {
      await adminAPI.revertRequirementActionLinks(pid, rid);
      toast.success('Reverted to registry defaults');
      await loadPreview();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Revert failed', { critical: true });
    } finally {
      setBusy(false);
    }
  };

  const fillFromRegistry = () => {
    if (!preview?.registry_default_links) {
      toast.error('Load preview first');
      return;
    }
    setDraftJson(JSON.stringify(preview.registry_default_links, null, 2));
  };

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Ops — Requirement action links</h1>
          <p className="text-gray-600 text-sm mt-2 max-w-3xl">
            Owner/Admin only. Preview registry vs override, edit a <strong>draft</strong>, validate, <strong>publish</strong> to
            live resolver output, or <strong>revert</strong> to JSON catalog defaults. After publish, confirm in client{' '}
            <strong>Requirements</strong> and <strong>Today</strong> for the same property jurisdiction.
          </p>
        </div>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">property_id</label>
            <input
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-72 font-mono"
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
              placeholder="prop_…"
            />
          </div>
          <Button type="button" variant="outline" size="sm" onClick={loadRequirementsLite} disabled={loading}>
            Load requirements
          </Button>
        </div>
        {reqItems.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">requirement_id</label>
            <select
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm min-w-[320px] bg-white font-mono"
              value={requirementId}
              onChange={(e) => setRequirementId(e.target.value)}
            >
              <option value="">Select…</option>
              {reqItems.map((it) => (
                <option key={it.requirement_id} value={it.requirement_id}>
                  {it.requirement_id} · {it.requirement_code || it.requirement_type || '—'} · {it.status || '—'}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={loadPreview} disabled={loading || busy}>
            Load preview
          </Button>
          <Link to="/admin/ops/compliance" className="text-sm text-electric-teal hover:underline self-center">
            Compliance snapshot
          </Link>
          <Link to="/admin/ops" className="text-sm text-electric-teal hover:underline self-center">
            Ops overview
          </Link>
        </div>

        {preview && (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 bg-slate-50/80 p-4 text-sm">
              <p>
                <span className="font-medium text-gray-800">Portfolio jurisdiction:</span>{' '}
                {preview.portfolio_jurisdiction_label || '—'}
              </p>
              <p>
                <span className="font-medium text-gray-800">Resolved region token:</span> {preview.resolved_region}
              </p>
              <p>
                <span className="font-medium text-gray-800">Registry key:</span> {preview.registry_key || '—'} ·{' '}
                <span className="font-medium text-gray-800">Code:</span> {preview.requirement_code || '—'}
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <LinksTable title="Registry default (raw JSON block)" rows={preview.registry_default_links} />
              <LinksTable title="Published override (stored)" rows={preview.override_published} />
              <LinksTable title="Draft override (stored)" rows={preview.override_draft} />
              <JsonBlock title="Final client shape (≤2, jurisdiction-filtered)" data={preview.effective_final_client_shape} />
            </div>
            <div className="grid md:grid-cols-3 gap-4">
              <JsonBlock title="Effective from registry only" data={preview.effective_from_registry_default} />
              <JsonBlock title="Effective from published override" data={preview.effective_from_published_override} />
              <JsonBlock title="Effective if draft were published" data={preview.effective_if_draft_published} />
            </div>

            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <h2 className="text-sm font-semibold text-gray-800">Draft editor (JSON array)</h2>
                <Button type="button" variant="outline" size="sm" onClick={fillFromRegistry}>
                  Hydrate from registry block
                </Button>
              </div>
              <textarea
                className="w-full min-h-[220px] border border-gray-200 rounded-lg p-3 text-xs font-mono"
                value={draftJson}
                onChange={(e) => setDraftJson(e.target.value)}
                spellCheck={false}
              />
              <p className="text-xs text-gray-500 mt-1">
                Editable fields per item: key, label, url, jurisdictions, is_active, priority, kind (optional). URLs must be
                http(s). Max 2 active links per region; duplicate keys and duplicate URLs overlapping a region are rejected.
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button type="button" onClick={saveDraft} disabled={busy}>
                  Save draft
                </Button>
                <Button type="button" variant="secondary" onClick={publish} disabled={busy}>
                  Publish draft
                </Button>
                <Button type="button" variant="destructive" onClick={revert} disabled={busy}>
                  Revert to registry default
                </Button>
              </div>
            </div>

            <div>
              <h2 className="text-sm font-semibold text-gray-800 mb-2">Embedded audit (registry_metadata.action_links_audit)</h2>
              <JsonBlock title="Last entries" data={preview.action_links_audit} />
            </div>
          </div>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
