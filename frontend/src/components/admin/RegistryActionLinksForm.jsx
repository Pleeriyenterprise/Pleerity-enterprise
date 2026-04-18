import React from 'react';
import { Button } from '../ui/button';

const REGIONS = ['ENGLAND', 'WALES', 'SCOTLAND', 'NORTHERN_IRELAND'];
/** Canonical kinds only (aligned with registry validation / publish). */
const KINDS = [
  { value: 'official', label: 'Official' },
  { value: 'directory', label: 'Directory' },
  { value: 'partner', label: 'Partner' },
];

const emptyLink = () => ({
  key: '',
  label: '',
  url: '',
  kind: 'official',
  jurisdictions: ['ENGLAND'],
  priority: 100,
  is_active: true,
});

/**
 * @param {{ value: any[], onChange: (v: any[]) => void, disabled?: boolean, previewRegion?: string }} props
 */
export default function RegistryActionLinksForm({ value, onChange, disabled, previewRegion = 'ENGLAND' }) {
  const rows = Array.isArray(value) && value.length > 0 ? value : [emptyLink()];

  const setRows = (next) => {
    onChange(next);
  };

  const update = (i, patch) => {
    const n = rows.map((r, j) => (j === i ? { ...r, ...patch } : r));
    setRows(n);
  };

  const add = () => {
    setRows([...rows, emptyLink()]);
  };

  const remove = (i) => {
    const n = rows.filter((_, j) => j !== i);
    setRows(n.length ? n : [emptyLink()]);
  };

  const toggleJur = (i, reg) => {
    const r = rows[i] || {};
    const cur = Array.isArray(r.jurisdictions) ? [...r.jurisdictions] : [];
    const up = reg.toUpperCase();
    if (cur.includes(up)) {
      const next = cur.filter((x) => x !== up);
      update(i, { jurisdictions: next.length ? next : [up] });
    } else {
      update(i, { jurisdictions: [...cur, up] });
    }
  };

  const pre = String(previewRegion || 'ENGLAND')
    .trim()
    .toUpperCase();
  const activeForPreview = (row) => {
    if (row.is_active === false) return false;
    const j = row.jurisdictions;
    if (!Array.isArray(j) || !j.length) return false;
    return j.map((x) => String(x).toUpperCase()).includes(pre);
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-600 border border-slate-200 rounded-md p-2 bg-slate-50/80">
        <strong>Resolver precedence (highest first):</strong> (1) per-requirement manual override in Mongo
        (emergency / ticketed), (2) <span className="font-mono">action_links</span> from the active published
        registry snapshot, (3) static <span className="font-mono">presentation/requirements_action_links.json</span>{' '}
        fallback. This form edits the draft that flows into (2) after publish.
        <span className="block mt-1 text-slate-700">
          <strong>Kind</strong> is a controlled enum (<span className="font-mono">official</span>,{' '}
          <span className="font-mono">directory</span>, <span className="font-mono">partner</span>);{' '}
          <strong>jurisdictions</strong> must be the four UK region codes;           <strong>priority</strong> is an integer (-1000000–1000000).
        </span>
      </p>
      {rows.map((row, i) => {
        const kRaw = String(row.kind || 'official').toLowerCase();
        const kindOptions = KINDS.some((k) => k.value === kRaw)
          ? KINDS
          : [{ value: kRaw, label: `${kRaw} (legacy — pick canonical)` }, ...KINDS];
        return (
        <div
          key={`${i}-${row.key || 'row'}`}
          className="border border-gray-200 rounded-lg p-3 space-y-2 bg-white"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <label className="block text-xs">
              <span className="text-gray-500">Key (unique)</span>
              <input
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm font-mono"
                value={row.key || ''}
                onChange={(e) => update(i, { key: e.target.value })}
                disabled={disabled}
                placeholder="e.g. epc_england_guidance"
              />
            </label>
            <label className="block text-xs">
              <span className="text-gray-500">Label</span>
              <input
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                value={row.label || ''}
                onChange={(e) => update(i, { label: e.target.value })}
                disabled={disabled}
              />
            </label>
            <label className="block text-xs sm:col-span-2">
              <span className="text-gray-500">URL (https…)</span>
              <input
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                value={row.url || ''}
                onChange={(e) => update(i, { url: e.target.value })}
                disabled={disabled}
                placeholder="https://"
              />
            </label>
            <label className="block text-xs">
              <span className="text-gray-500">Kind</span>
              <select
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                value={kRaw}
                onChange={(e) => update(i, { kind: e.target.value })}
                disabled={disabled}
              >
                {kindOptions.map((k) => (
                  <option key={k.value} value={k.value}>
                    {k.label} ({k.value})
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs">
              <span className="text-gray-500">Priority (lower = first when ties)</span>
              <input
                type="number"
                min={-1000000}
                max={1000000}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                value={row.priority != null ? row.priority : 100}
                onChange={(e) => update(i, { priority: Number(e.target.value) || 0 })}
                disabled={disabled}
              />
            </label>
          </div>
          <div>
            <span className="text-xs text-gray-500 block mb-1">Jurisdictions (region scope)</span>
            <div className="flex flex-wrap gap-2">
              {REGIONS.map((reg) => (
                <label key={reg} className="inline-flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={Array.isArray(row.jurisdictions) && row.jurisdictions.map((x) => String(x).toUpperCase()).includes(reg)}
                    onChange={() => toggleJur(i, reg)}
                    disabled={disabled}
                  />
                  {reg}
                </label>
              ))}
            </div>
          </div>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={row.is_active !== false}
              onChange={(e) => update(i, { is_active: e.target.checked })}
              disabled={disabled}
            />
            Active
          </label>
          <div className="flex justify-end">
            <Button type="button" variant="outline" size="sm" onClick={() => remove(i)} disabled={disabled}>
              Remove link
            </Button>
          </div>
        </div>
        );
      })}
      <div className="flex flex-wrap gap-2 items-center">
        <Button type="button" size="sm" variant="secondary" onClick={add} disabled={disabled}>
          Add action link
        </Button>
        <span className="text-xs text-gray-500">
          Preview region <span className="font-mono">{pre}</span>:{' '}
          {rows
            .filter((r) => activeForPreview(r) && (r.label || r.url))
            .sort((a, b) => (a.priority || 100) - (b.priority || 100))
            .map((r) => r.label || r.key)
            .join(' · ') || '— no active links for this region'}
        </span>
      </div>
    </div>
  );
}
