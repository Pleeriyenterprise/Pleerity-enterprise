import React, { useEffect, useState, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from 'sonner';

function Section({ title, children }) {
  return (
    <section className="border border-gray-200 rounded-lg p-4 mb-4 bg-white">
      <h2 className="text-sm font-semibold text-gray-800 mb-3">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, value, onChange, disabled, textarea }) {
  const common = {
    disabled,
    className: 'w-full border border-gray-200 rounded-md px-2 py-1.5 text-sm',
  };
  return (
    <label className="block mb-3">
      <span className="text-xs text-gray-500 block mb-1">{label}</span>
      {textarea ? (
        <textarea {...common} rows={4} value={value} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input {...common} value={value} onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
  );
}

export default function AdminComplianceRegistryEditorPage() {
  const { entryId } = useParams();
  const { isOwner, isAdmin } = useAuth();
  const canMutate = Boolean(isOwner?.() || isAdmin?.());
  const [draft, setDraft] = useState(null);
  const [compare, setCompare] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actionLinksJson, setActionLinksJson] = useState('[]');
  const [conditionsText, setConditionsText] = useState('{}');
  const [whyByJurisdictionText, setWhyByJurisdictionText] = useState('{}');

  const load = useCallback(() => {
    if (!entryId) return;
    setLoading(true);
    Promise.all([
      adminAPI.getComplianceRegistryDraft(entryId),
      adminAPI.getComplianceRegistryDraftCompare(entryId),
    ])
      .then(([dRes, cRes]) => {
        setDraft(dRes.data);
        setCompare(cRes.data);
        setActionLinksJson(JSON.stringify(dRes.data?.action_links || [], null, 2));
        setConditionsText(JSON.stringify(dRes.data?.conditions || {}, null, 2));
        setWhyByJurisdictionText(JSON.stringify(dRes.data?.why_it_matters_by_jurisdiction || {}, null, 2));
      })
      .catch((err) => {
        toast.error(err?.response?.data?.detail || 'Failed to load draft');
        setDraft(null);
      })
      .finally(() => setLoading(false));
  }, [entryId]);

  useEffect(() => {
    load();
  }, [load]);

  const setIdentity = (k, v) => {
    setDraft((prev) => ({ ...prev, identity: { ...prev.identity, [k]: v } }));
  };
  const setClassification = (k, v) => {
    setDraft((prev) => ({ ...prev, classification: { ...prev.classification, [k]: v } }));
  };
  const setJurisdiction = (k, v) => {
    setDraft((prev) => ({ ...prev, jurisdiction: { ...prev.jurisdiction, [k]: v } }));
  };
  const setFrequency = (k, v) => {
    setDraft((prev) => ({ ...prev, frequency: { ...prev.frequency, [k]: v } }));
  };
  const setActionBehaviour = (k, v) => {
    setDraft((prev) => ({ ...prev, action_behaviour: { ...prev.action_behaviour, [k]: v } }));
  };
  const setGovernance = (k, v) => {
    setDraft((prev) => ({ ...prev, governance: { ...prev.governance, [k]: v } }));
  };

  const save = () => {
    if (!canMutate || !draft) return;
    let links;
    let conditions;
    let whyByJurisdiction;
    try {
      links = JSON.parse(actionLinksJson || '[]');
    } catch {
      toast.error('Action links must be valid JSON');
      return;
    }
    try {
      conditions = JSON.parse(conditionsText || '{}');
    } catch {
      toast.error('Conditions must be valid JSON');
      return;
    }
    try {
      whyByJurisdiction = JSON.parse(whyByJurisdictionText || '{}');
    } catch {
      toast.error('Why it matters by jurisdiction must be valid JSON');
      return;
    }
    const patch = {
      identity: draft.identity,
      classification: draft.classification,
      jurisdiction: draft.jurisdiction,
      conditions,
      frequency: draft.frequency,
      action_behaviour: draft.action_behaviour,
      action_links: Array.isArray(links) ? links : [],
      why_it_matters_short: draft.why_it_matters_short || '',
      why_it_matters_long: draft.why_it_matters_long || '',
      why_it_matters_by_jurisdiction: whyByJurisdiction && typeof whyByJurisdiction === 'object' ? whyByJurisdiction : {},
      governance: draft.governance,
    };
    setSaving(true);
    adminAPI
      .patchComplianceRegistryDraft(entryId, { patch })
      .then((res) => {
        setDraft(res.data);
        setConditionsText(JSON.stringify(res.data?.conditions || {}, null, 2));
        setActionLinksJson(JSON.stringify(res.data?.action_links || [], null, 2));
        setWhyByJurisdictionText(JSON.stringify(res.data?.why_it_matters_by_jurisdiction || {}, null, 2));
        toast.success('Saved');
        return adminAPI.getComplianceRegistryDraftCompare(entryId);
      })
      .then((cRes) => setCompare(cRes.data))
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(Array.isArray(d?.errors) ? d.errors.join('; ') : typeof d === 'string' ? d : 'Save failed');
      })
      .finally(() => setSaving(false));
  };

  if (loading) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">Loading…</div>
      </UnifiedAdminLayout>
    );
  }

  if (!draft) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">
          <p className="text-gray-600">Draft not found.</p>
          <Link to="/admin/compliance/registry" className="text-electric-teal text-sm">
            ← Back to list
          </Link>
        </div>
      </UnifiedAdminLayout>
    );
  }

  const diffRows = compare?.diff || [];

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-5xl">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <Link to="/admin/compliance/registry" className="text-sm text-electric-teal hover:underline">
            ← Requirement Registry
          </Link>
          <Link to="/admin/compliance/registry/preview" className="text-sm text-electric-teal hover:underline">
            Preview &amp; simulation
          </Link>
          <span className="text-gray-300">|</span>
          <h1 className="text-xl font-bold text-gray-900 font-mono">{draft.canonical_code}</h1>
          <span className="text-sm text-gray-500 font-mono">scope: {draft.scope_key}</span>
          {canMutate && (
            <Button className="ml-auto" size="sm" onClick={save} disabled={saving}>
              {saving ? 'Saving…' : 'Save draft'}
            </Button>
          )}
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50/90 px-3 py-2 mb-4 text-xs text-amber-950">
          <strong>Draft governance only.</strong> Edits here are stored as Mongo drafts and do not change live client
          generation. The planner and materialiser still use the in-code registry until a future publish and integration
          path exists. Compare below is for drift review against that engine baseline.
        </div>

        <Section title="Identity">
          <Field label="Name" value={draft.identity?.name || ''} onChange={(v) => setIdentity('name', v)} disabled={!canMutate} />
          <Field label="Category" value={draft.identity?.category || ''} onChange={(v) => setIdentity('category', v)} disabled={!canMutate} />
          <Field
            label="Description"
            value={draft.identity?.description || ''}
            onChange={(v) => setIdentity('description', v)}
            disabled={!canMutate}
            textarea
          />
          <Field
            label="Legal reference (draft metadata only)"
            value={draft.identity?.legal_reference || ''}
            onChange={(v) => setIdentity('legal_reference', v)}
            disabled={!canMutate}
          />
        </Section>

        <Section title="Classification">
          <Field
            label="Requirement type (DOCUMENT | JOB | OBLIGATION | SYSTEM)"
            value={draft.classification?.requirement_type || ''}
            onChange={(v) => setClassification('requirement_type', v)}
            disabled={!canMutate}
          />
          <Field
            label="Criticality (HIGH | MEDIUM | LOW)"
            value={draft.classification?.criticality || ''}
            onChange={(v) => setClassification('criticality', v)}
            disabled={!canMutate}
          />
          <div className="flex gap-4 mb-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!draft.classification?.requires_document}
                onChange={(e) => setClassification('requires_document', e.target.checked)}
                disabled={!canMutate}
              />
              Requires document
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!draft.classification?.requires_job}
                onChange={(e) => setClassification('requires_job', e.target.checked)}
                disabled={!canMutate}
              />
              Requires job
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={draft.classification?.client_surface_visible !== false}
                onChange={(e) => setClassification('client_surface_visible', e.target.checked)}
                disabled={!canMutate}
              />
              Client visible
            </label>
          </div>
        </Section>

        <Section title="Jurisdiction">
          <Field
            label="Display jurisdictions (comma-separated: England, Wales, Scotland, Northern Ireland)"
            value={(draft.jurisdiction?.display_jurisdictions || []).join(', ')}
            onChange={(v) =>
              setJurisdiction(
                'display_jurisdictions',
                v
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean),
              )
            }
            disabled={!canMutate}
          />
          <Field
            label="Scoring / engine bucket note"
            value={draft.jurisdiction?.scoring_jurisdiction_note || ''}
            onChange={(v) => setJurisdiction('scoring_jurisdiction_note', v)}
            disabled={!canMutate}
            textarea
          />
        </Section>

        <Section title="Conditions (JSON)">
          <Field
            label="conditions object"
            value={conditionsText}
            onChange={setConditionsText}
            disabled={!canMutate}
            textarea
          />
        </Section>

        <Section title="Frequency">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field
              label="Frequency days"
              value={String(draft.frequency?.frequency_days ?? '')}
              onChange={(v) => setFrequency('frequency_days', v === '' ? null : Number(v))}
              disabled={!canMutate}
            />
            <Field
              label="Reminder lead days"
              value={String(draft.frequency?.reminder_lead_days ?? '')}
              onChange={(v) => setFrequency('reminder_lead_days', v === '' ? null : Number(v))}
              disabled={!canMutate}
            />
          </div>
        </Section>

        <Section title="Action behaviour">
          <Field
            label="Primary action mode (upload_document | arrange_job | view_guidance | hidden)"
            value={draft.action_behaviour?.primary_action_mode || ''}
            onChange={(v) => setActionBehaviour('primary_action_mode', v)}
            disabled={!canMutate}
          />
          <Field
            label="CTA label override"
            value={draft.action_behaviour?.cta_label_override || ''}
            onChange={(v) => setActionBehaviour('cta_label_override', v)}
            disabled={!canMutate}
          />
        </Section>

        <Section title="Action links (JSON array; validated server-side)">
          <Field label="action_links" value={actionLinksJson} onChange={setActionLinksJson} disabled={!canMutate} textarea />
        </Section>

        <Section title="Why it matters">
          <Field
            label="Short explanation (required for client-visible actionable requirements)"
            value={draft.why_it_matters_short || ''}
            onChange={(v) => setDraft((prev) => ({ ...prev, why_it_matters_short: v }))}
            disabled={!canMutate}
          />
          <Field
            label="Detailed explanation"
            value={draft.why_it_matters_long || ''}
            onChange={(v) => setDraft((prev) => ({ ...prev, why_it_matters_long: v }))}
            disabled={!canMutate}
            textarea
          />
          <Field
            label='Jurisdiction overrides JSON (e.g. {"SCOTLAND":{"short":"...","long":"..."}})'
            value={whyByJurisdictionText}
            onChange={setWhyByJurisdictionText}
            disabled={!canMutate}
            textarea
          />
        </Section>

        <Section title="Notes / change reason">
          <Field
            label="Change reason"
            value={draft.governance?.change_reason || ''}
            onChange={(v) => setGovernance('change_reason', v)}
            disabled={!canMutate}
            textarea
          />
          <Field
            label="Internal notes"
            value={draft.governance?.internal_notes || ''}
            onChange={(v) => setGovernance('internal_notes', v)}
            disabled={!canMutate}
            textarea
          />
          <Field
            label="Legal source summary"
            value={draft.governance?.legal_source_summary || ''}
            onChange={(v) => setGovernance('legal_source_summary', v)}
            disabled={!canMutate}
            textarea
          />
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded p-2">
            Needs review fields: {(draft.governance?.needs_review_fields || []).join(', ') || '—'}
          </p>
        </Section>

        <Section title="Compare — draft vs engine baseline (read-only)">
          <p className="text-xs text-gray-500 mb-2">
            Published column is the in-code compliance_rules_registry (+ action link catalogue), not Mongo drafts.
          </p>
          <div className="overflow-x-auto max-h-80 overflow-y-auto border border-gray-100 rounded">
            <table className="w-full text-xs text-left">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="p-2">Path</th>
                  <th className="p-2">Draft</th>
                  <th className="p-2">Baseline</th>
                  <th className="p-2">Δ</th>
                </tr>
              </thead>
              <tbody>
                {diffRows.map((r) => (
                  <tr key={r.path} className={r.changed ? 'bg-amber-50' : ''}>
                    <td className="p-2 font-mono whitespace-nowrap">{r.path}</td>
                    <td className="p-2 break-all">{typeof r.draft === 'object' ? JSON.stringify(r.draft) : String(r.draft)}</td>
                    <td className="p-2 break-all">
                      {typeof r.published_baseline === 'object'
                        ? JSON.stringify(r.published_baseline)
                        : String(r.published_baseline)}
                    </td>
                    <td className="p-2">{r.changed ? 'yes' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      </div>
    </UnifiedAdminLayout>
  );
}
