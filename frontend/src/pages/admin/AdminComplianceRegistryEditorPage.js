import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import PrepareRegistryPublishDialog from '../../components/admin/PrepareRegistryPublishDialog';
import RegistryActionLinksForm from '../../components/admin/RegistryActionLinksForm';
import RegistryConditionsBuilder from '../../components/admin/RegistryConditionsBuilder';
import { REGISTRY_CONDITION_BUILDER_FALLBACK } from '../../data/registryConditionBuilderFallback';
import { adminAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from '@/utils/portalNotifications';
import {
  buildEffectiveJurisdictionsSummary,
  displayRegionsCoverAllUK,
  formatScopeKeyLabel,
} from '../../utils/complianceRegistryOperatorUi';
import { humanSummaryRegistryConditions } from '../../utils/registryConditionsSummary';

function sanitizeConditionsForSave(cond) {
  if (!cond || typeof cond !== 'object') return { logic: 'ALL', rules: [] };
  const logic = String(cond.logic || 'ALL').toUpperCase() === 'ANY' ? 'ANY' : 'ALL';
  const rules = (Array.isArray(cond.rules) ? cond.rules : [])
    .filter((r) => r && typeof r === 'object' && String(r.field || '').trim() && String(r.op || '').trim())
    .map((r) => {
      const field = String(r.field).trim();
      const op = String(r.op).trim();
      if (op === 'true' || op === 'false') return { field, op };
      return { field, op, value: r.value };
    });
  return { logic, rules };
}

/** Drop placeholder rows the UI adds (empty key/label/url) so PATCH does not send invalid rows that fail validation. */
function stripEmptyActionLinkPlaceholders(links) {
  if (!Array.isArray(links)) return [];
  return links.filter((row) => {
    if (!row || typeof row !== 'object') return false;
    const label = String(row.label ?? '').trim();
    const url = String(row.url ?? '').trim();
    const key = String(row.key ?? '').trim();
    return Boolean(label || url || key);
  });
}

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

/** Mirrors ``controlled_field_options_payload`` in backend (fallback if options API fails). */
const FALLBACK_CONTROLLED_OPTIONS = {
  identity_categories: [
    { value: 'ELECTRICAL', label: 'Electrical' },
    { value: 'GAS', label: 'Gas' },
    { value: 'FIRE', label: 'Fire safety' },
    { value: 'HEALTH', label: 'Health' },
    { value: 'REGULATORY', label: 'Regulatory / statutory' },
    { value: 'ENERGY', label: 'Energy' },
    { value: 'TENANCY', label: 'Tenancy' },
    { value: 'LICENSING', label: 'Licensing' },
    { value: 'SAFETY', label: 'Safety' },
    { value: 'OTHER', label: 'Other' },
  ],
  requirement_types: [
    { value: 'DOCUMENT', label: 'Document' },
    { value: 'JOB', label: 'Job' },
    { value: 'OBLIGATION', label: 'Obligation' },
    { value: 'SYSTEM', label: 'System' },
  ],
  criticality: [
    { value: 'HIGH', label: 'High' },
    { value: 'MEDIUM', label: 'Medium' },
    { value: 'LOW', label: 'Low' },
  ],
  uk_display_regions: [
    { value: 'ENGLAND', label: 'England' },
    { value: 'SCOTLAND', label: 'Scotland' },
    { value: 'WALES', label: 'Wales' },
    { value: 'NORTHERN_IRELAND', label: 'Northern Ireland' },
  ],
  primary_action_modes: [
    { value: 'upload_document', label: 'Upload document' },
    { value: 'arrange_job', label: 'Arrange job' },
    { value: 'view_guidance', label: 'View guidance' },
    { value: 'hidden', label: 'Hidden' },
  ],
};

function ControlledEnumSelect({ label, help, value, options, onChange, disabled, unknownValue }) {
  const v = value == null ? '' : String(value);
  const known = (options || []).some((o) => o.value === v);
  return (
    <label className="block mb-3">
      <span className="text-xs text-gray-500 block mb-1">{label}</span>
      {help ? <p className="text-[11px] text-slate-600 mb-1">{help}</p> : null}
      <select
        disabled={disabled}
        className="w-full border border-gray-200 rounded-md px-2 py-1.5 text-sm bg-white"
        value={known ? v : v || ''}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">— Select —</option>
        {(options || []).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label} ({o.value})
          </option>
        ))}
        {!known && v ? (
          <option value={v}>
            {unknownValue || v} (not in current list — save may fail until replaced)
          </option>
        ) : null}
      </select>
    </label>
  );
}

function JurisdictionCheckboxes({ label, help, regionDefs, selected, onChange, disabled }) {
  const sel = new Set((selected || []).map((x) => String(x || '').trim().toUpperCase()).filter(Boolean));
  const toggle = (code) => {
    const next = new Set(sel);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    const ordered = (regionDefs || []).map((r) => r.value).filter((c) => next.has(c));
    onChange(ordered);
  };
  return (
    <div className="mb-3">
      <span className="text-xs text-gray-500 block mb-1">{label}</span>
      {help ? <p className="text-[11px] text-slate-600 mb-2">{help}</p> : null}
      <div className="flex flex-wrap gap-3">
        {(regionDefs || []).map((r) => (
          <label key={r.value} className="inline-flex items-center gap-2 text-sm text-gray-800">
            <input type="checkbox" checked={sel.has(r.value)} onChange={() => toggle(r.value)} disabled={disabled} />
            <span>
              {r.label} <span className="text-xs text-gray-400 font-mono">({r.value})</span>
            </span>
          </label>
        ))}
      </div>
    </div>
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
  const [linkPreviewRegion, setLinkPreviewRegion] = useState('ENGLAND');
  const [showLinksAdvanced, setShowLinksAdvanced] = useState(false);
  const [showConditionsAdvanced, setShowConditionsAdvanced] = useState(false);
  const [fieldOptions, setFieldOptions] = useState(null);
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);

  const opts = useMemo(() => {
    const fo = fieldOptions || {};
    return {
      ...FALLBACK_CONTROLLED_OPTIONS,
      ...fo,
      condition_fields:
        fo.condition_fields?.length > 0 ? fo.condition_fields : REGISTRY_CONDITION_BUILDER_FALLBACK.condition_fields,
      condition_logic_options:
        fo.condition_logic_options?.length > 0
          ? fo.condition_logic_options
          : REGISTRY_CONDITION_BUILDER_FALLBACK.condition_logic_options,
      condition_templates:
        fo.condition_templates?.length > 0
          ? fo.condition_templates
          : REGISTRY_CONDITION_BUILDER_FALLBACK.condition_templates,
    };
  }, [fieldOptions]);

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
        toast.error(err?.response?.data?.detail || 'Failed to load draft', { critical: true });
        setDraft(null);
      })
      .finally(() => setLoading(false));
  }, [entryId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    adminAPI
      .getComplianceRegistryControlledFieldOptions()
      .then((r) => setFieldOptions(r.data))
      .catch(() => {
        /* FALLBACK_CONTROLLED_OPTIONS */
      });
  }, []);

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

  const handleConditionsBuilderChange = (next) => {
    setDraft((prev) => ({ ...prev, conditions: next }));
  };

  const save = () => {
    if (!canMutate || !draft) return;
    let links;
    let conditions;
    let whyByJurisdiction;
    if (showLinksAdvanced) {
      try {
        links = JSON.parse(actionLinksJson || '[]');
      } catch {
        toast.error('Action links must be valid JSON');
        return;
      }
      if (!Array.isArray(links)) {
        toast.error('action_links must be a JSON array');
        return;
      }
    } else {
      links = Array.isArray(draft.action_links) ? draft.action_links : [];
    }
    links = stripEmptyActionLinkPlaceholders(links);
    if (showConditionsAdvanced) {
      try {
        conditions = JSON.parse(conditionsText || '{}');
      } catch {
        toast.error('Conditions must be valid JSON');
        return;
      }
    } else {
      conditions = sanitizeConditionsForSave(draft.conditions);
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
      action_links: links,
      why_it_matters_short: draft.why_it_matters_short || '',
      why_it_matters_long: draft.why_it_matters_long || '',
      why_it_matters_by_jurisdiction: whyByJurisdiction && typeof whyByJurisdiction === 'object' ? whyByJurisdiction : {},
      governance: draft.governance,
    };
    setSaving(true);
    adminAPI
      .patchComplianceRegistryDraft(entryId, { patch })
      .then((res) => {
        const { normalisation_warnings: nw, ...rest } = res.data || {};
        const savedLinks = Array.isArray(rest.action_links)
          ? rest.action_links
          : Array.isArray(patch.action_links)
            ? patch.action_links
            : [];
        const mergedRest = { ...rest, action_links: savedLinks };
        setDraft(mergedRest);
        setConditionsText(JSON.stringify(mergedRest?.conditions || { logic: 'ALL', rules: [] }, null, 2));
        setActionLinksJson(JSON.stringify(savedLinks, null, 2));
        setWhyByJurisdictionText(JSON.stringify(mergedRest?.why_it_matters_by_jurisdiction || {}, null, 2));
        toast.success('Saved');
        if (Array.isArray(nw) && nw.length) {
          toast.info('Legacy values normalised', { description: nw.join(' · ') });
        }
        return adminAPI.getComplianceRegistryDraftCompare(entryId);
      })
      .then((cRes) => setCompare(cRes.data))
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(Array.isArray(d?.errors) ? d.errors.join('; ') : typeof d === 'string' ? d : 'Save failed', {
          critical: true,
        });
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
  const displayRegs = draft.jurisdiction?.display_jurisdictions;
  const broadWarning = displayRegionsCoverAllUK(displayRegs);
  const effJur = buildEffectiveJurisdictionsSummary(draft);
  const scopeReadable = formatScopeKeyLabel(draft.scope_key);

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
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-gray-900 leading-tight">{draft.identity?.name || 'Requirement'}</h1>
            <p className="text-xs text-gray-500 font-mono mt-0.5">
              {draft.canonical_code} · scope {draft.scope_key} <span className="text-gray-400">({scopeReadable})</span>
            </p>
          </div>
          {canMutate && (
            <div className="ml-auto flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => setPublishDialogOpen(true)}>
                Publish path…
              </Button>
              <Button size="sm" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save draft'}
              </Button>
            </div>
          )}
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50/90 px-3 py-2 mb-4 text-xs text-amber-950">
          <strong>Draft (editable) — not live until published.</strong> Saving writes Mongo only. After Owner{' '}
          <strong>Publish queue</strong> activation, this line’s snapshot <strong>merges into</strong> the active
          published registry map (other keys already live remain unless a later publish replaces them). The planner and
          resolver read that map immediately. <strong>Per-property Mongo requirement rows are not bulk-rewritten</strong>{' '}
          — use per-property sync/materialise when a site must pick up changed copy or action links.
          <span className="block mt-1 text-amber-900/95">
            Category, requirement type, criticality, UK regions, primary action mode, and action-link kinds are{' '}
            <strong>controlled system values</strong> (same lists as validation / publish). Narrative fields (name,
            descriptions, legal reference, notes, conditions JSON) stay free-form.
          </span>
        </div>
        {broadWarning && (
          <div className="rounded-md border border-amber-300 bg-amber-100/80 px-3 py-2 mb-4 text-xs text-amber-950">
            <strong>Wide jurisdiction coverage:</strong> this line lists all four UK regions. Confirm that is intentional
            before publish — a broad rule will surface everywhere the planner applies it.
          </div>
        )}
        <div className="rounded-md border border-slate-200 bg-slate-50/90 px-3 py-2 mb-4 text-xs text-slate-800">
          <strong>Effective jurisdictions (summary):</strong> {effJur}
        </div>

        <Section title="Preview as client sees it (summary)">
          <p className="text-xs text-gray-600 mb-2">
            High-level copy of what operators configure — not a full portal render. Uses the same canonical values as
            validation and publish.
          </p>
          <ul className="text-sm text-gray-800 space-y-1 list-disc pl-5">
            <li>
              <span className="font-medium">Name:</span> {draft.identity?.name || '—'}
            </li>
            <li>
              <span className="font-medium">Category:</span>{' '}
              {opts.identity_categories?.find((o) => o.value === draft.identity?.category)?.label ||
                draft.identity?.category ||
                '—'}
            </li>
            <li>
              <span className="font-medium">Requirement type:</span>{' '}
              {opts.requirement_types?.find((o) => o.value === draft.classification?.requirement_type)?.label ||
                draft.classification?.requirement_type ||
                '—'}
            </li>
            <li>
              <span className="font-medium">Criticality:</span> {draft.classification?.criticality || '—'}
            </li>
            <li>
              <span className="font-medium">Regions (stored):</span>{' '}
              {(draft.jurisdiction?.display_jurisdictions || [])
                .map((c) => opts.uk_display_regions?.find((o) => o.value === c)?.label || c)
                .join(', ') || '—'}
            </li>
            <li>
              <span className="font-medium">Primary action:</span>{' '}
              {opts.primary_action_modes?.find((o) => o.value === draft.action_behaviour?.primary_action_mode)?.label ||
                draft.action_behaviour?.primary_action_mode ||
                '—'}
            </li>
            <li>
              <span className="font-medium">Why it matters (short):</span>{' '}
              {(draft.why_it_matters_short || '').slice(0, 160)}
              {(draft.why_it_matters_short || '').length > 160 ? '…' : ''}
            </li>
          </ul>
        </Section>

        <Section title="Identity">
          <Field label="Name" value={draft.identity?.name || ''} onChange={(v) => setIdentity('name', v)} disabled={!canMutate} />
          <ControlledEnumSelect
            label="Category"
            help="Controlled taxonomy — stored values are uppercase system tokens (aligned with validation and publish)."
            value={draft.identity?.category || ''}
            options={opts.identity_categories}
            onChange={(v) => setIdentity('category', v)}
            disabled={!canMutate}
            unknownValue={draft.identity?.category}
          />
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
          <ControlledEnumSelect
            label="Requirement type"
            help="Strict enum — drives planner materialisation shape and client surfaces."
            value={draft.classification?.requirement_type || ''}
            options={opts.requirement_types}
            onChange={(v) => setClassification('requirement_type', v)}
            disabled={!canMutate}
            unknownValue={draft.classification?.requirement_type}
          />
          <ControlledEnumSelect
            label="Criticality"
            help="Strict enum — portfolio and alerting weighting."
            value={draft.classification?.criticality || ''}
            options={opts.criticality}
            onChange={(v) => setClassification('criticality', v)}
            disabled={!canMutate}
            unknownValue={draft.classification?.criticality}
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

        <Section title="Jurisdiction (safety)">
          <p className="text-xs text-gray-600 mb-2">
            <strong>display_jurisdictions</strong> is where this row applies in the client. It is independent of the{' '}
            <span className="font-mono">scope_key</span> merge bucket: <span className="font-mono">DEFAULT</span> is the
            usual shared line, not an automatic “all properties” override — the region list must still be explicit to
            publish safely.
          </p>
          <JurisdictionCheckboxes
            label="Display jurisdictions (stored as canonical UK codes)"
            help="Select one or more of the four UK regions. Free-text region lists are not accepted — saves and publish use these tokens only."
            regionDefs={opts.uk_display_regions}
            selected={draft.jurisdiction?.display_jurisdictions || []}
            onChange={(list) => setJurisdiction('display_jurisdictions', list)}
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

        <Section title="Conditions (applicability)">
          {!showConditionsAdvanced ? (
            <>
              <RegistryConditionsBuilder
                value={draft.conditions || { logic: 'ALL', rules: [] }}
                onChange={handleConditionsBuilderChange}
                disabled={!canMutate}
                fieldMeta={opts.condition_fields}
                logicOptions={opts.condition_logic_options}
                templates={opts.condition_templates}
              />
              <button
                type="button"
                className="text-xs text-electric-teal hover:underline mt-2"
                onClick={() => {
                  setConditionsText(JSON.stringify(draft.conditions || { logic: 'ALL', rules: [] }, null, 2));
                  setShowConditionsAdvanced(true);
                }}
              >
                Show raw JSON (advanced)
              </button>
            </>
          ) : (
            <>
              <p className="text-xs text-amber-900 bg-amber-50 border border-amber-100 rounded p-2 mb-2">
                Editing raw JSON bypasses the guided field list. Invalid conditions will be rejected on save with the
                same validation errors as publish.
              </p>
              <Field
                label="conditions object (logic + rules)"
                value={conditionsText}
                onChange={setConditionsText}
                disabled={!canMutate}
                textarea
              />
              <div className="flex flex-wrap gap-2 mt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    try {
                      const parsed = JSON.parse(conditionsText || '{}');
                      if (parsed == null || typeof parsed !== 'object' || Array.isArray(parsed)) {
                        toast.error('Conditions must be a JSON object');
                        return;
                      }
                      setDraft((prev) => ({ ...prev, conditions: parsed }));
                      setShowConditionsAdvanced(false);
                    } catch {
                      toast.error('Conditions must be valid JSON');
                    }
                  }}
                >
                  Apply JSON &amp; return to builder
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setConditionsText(JSON.stringify(draft.conditions || { logic: 'ALL', rules: [] }, null, 2));
                    setShowConditionsAdvanced(false);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </>
          )}
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
          <ControlledEnumSelect
            label="Primary action mode"
            help="Strict enum — controls default client CTA behaviour for this requirement."
            value={draft.action_behaviour?.primary_action_mode || ''}
            options={opts.primary_action_modes}
            onChange={(v) => setActionBehaviour('primary_action_mode', v)}
            disabled={!canMutate}
            unknownValue={draft.action_behaviour?.primary_action_mode}
          />
          <Field
            label="CTA label override"
            value={draft.action_behaviour?.cta_label_override || ''}
            onChange={(v) => setActionBehaviour('cta_label_override', v)}
            disabled={!canMutate}
          />
        </Section>

        <Section title="Action links (governed; preview below)">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-gray-600">Preview as region</span>
            <select
              className="border border-gray-200 rounded px-2 py-1 text-sm"
              value={linkPreviewRegion}
              onChange={(e) => setLinkPreviewRegion(e.target.value)}
            >
              {['ENGLAND', 'WALES', 'SCOTLAND', 'NORTHERN_IRELAND'].map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <RegistryActionLinksForm
            value={Array.isArray(draft.action_links) ? draft.action_links : []}
            onChange={(arr) => {
              setDraft((prev) => (prev ? { ...prev, action_links: arr } : prev));
              setActionLinksJson(JSON.stringify(arr, null, 2));
            }}
            disabled={!canMutate}
            previewRegion={linkPreviewRegion}
          />
          <button
            type="button"
            className="text-xs text-electric-teal hover:underline mt-2"
            onClick={() => {
              if (showLinksAdvanced) {
                try {
                  const parsed = JSON.parse(actionLinksJson || '[]');
                  if (!Array.isArray(parsed)) {
                    toast.error('action_links must be a JSON array');
                    return;
                  }
                  setDraft((prev) => (prev ? { ...prev, action_links: parsed } : prev));
                } catch {
                  toast.error('Fix action_links JSON before leaving advanced mode');
                  return;
                }
                setShowLinksAdvanced(false);
              } else {
                setShowLinksAdvanced(true);
              }
            }}
          >
            {showLinksAdvanced ? 'Hide' : 'Show'} raw JSON (advanced)
          </button>
          {showLinksAdvanced && (
            <div className="mt-2">
              <Field
                label="action_links JSON"
                value={actionLinksJson}
                onChange={(v) => {
                  setActionLinksJson(v);
                  try {
                    const parsed = JSON.parse(v || '[]');
                    if (Array.isArray(parsed)) {
                      setDraft((prev) => (prev ? { ...prev, action_links: parsed } : prev));
                    }
                  } catch {
                    /* partial JSON while typing — draft.action_links left unchanged until valid */
                  }
                }}
                disabled={!canMutate}
                textarea
              />
            </div>
          )}
        </Section>

        <Section title="Why it matters (client copy)">
          <p className="text-xs text-gray-600 mb-2">
            Shown (with jurisdiction overrides) on portal requirement surfaces via plan merge and explanation helpers.
            Keep short text scannable; use long for detail drawers. Compare below highlights when these differ from the
            engine-only baseline.
          </p>
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
            label='Jurisdiction-specific overrides (JSON) — e.g. {"SCOTLAND":{"short":"...","long":"..."}}'
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

        <Section title="Compare — draft vs in-code engine baseline (read-only)">
          <p className="text-xs text-gray-500 mb-2">
            Baseline column is the in-code <span className="font-mono">compliance_rules_registry</span> plus static action
            link JSON — not the Mongo draft. Rows with <span className="font-mono">why_it_matters</span> or action links
            are client-facing copy; changes there should be easy to spot.
          </p>
          <div className="text-xs text-slate-800 border border-slate-100 rounded-md p-2 mb-2 bg-slate-50/80 whitespace-pre-wrap">
            <span className="font-medium text-slate-700">Conditions (draft, readable):</span>{' '}
            {humanSummaryRegistryConditions(draft.conditions)}
          </div>
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
                {diffRows.map((r) => {
                  const why =
                    String(r.path || '').includes('why_it_matters') ||
                    r.path === 'action_links.length' ||
                    String(r.path || '').includes('conditions (human-readable)');
                  return (
                    <tr
                      key={r.path}
                      className={r.changed ? (why ? 'bg-teal-50/90 ring-1 ring-teal-200' : 'bg-amber-50') : ''}
                    >
                      <td className="p-2 font-mono whitespace-nowrap">{r.path}</td>
                      <td className={`p-2 break-all ${why ? 'whitespace-pre-wrap' : ''}`}>
                        {typeof r.draft === 'object' ? JSON.stringify(r.draft) : String(r.draft)}
                      </td>
                      <td className="p-2 break-all">
                        {typeof r.published_baseline === 'object'
                          ? JSON.stringify(r.published_baseline)
                          : String(r.published_baseline)}
                      </td>
                      <td className="p-2">{r.changed ? 'yes' : ''}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Section>

        <PrepareRegistryPublishDialog
          open={publishDialogOpen}
          onOpenChange={setPublishDialogOpen}
          entryId={draft?.entry_id}
          canonicalCode={draft?.canonical_code}
          scopeKey={draft?.scope_key}
          canMutate={canMutate}
        />
      </div>
    </UnifiedAdminLayout>
  );
}
