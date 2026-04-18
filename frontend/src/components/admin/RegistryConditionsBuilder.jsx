import React, { useMemo } from 'react';
import { Button } from '../ui/button';
import { humanSummaryRegistryConditions } from '../../utils/registryConditionsSummary';

function normalizeConditions(c) {
  if (!c || typeof c !== 'object') return { logic: 'ALL', rules: [] };
  const logic = String(c.logic || 'ALL').toUpperCase() === 'ANY' ? 'ANY' : 'ALL';
  const rules = Array.isArray(c.rules) ? c.rules.map((r) => ({ ...r })) : [];
  return { logic, rules };
}

/**
 * @param {{
 *   value: { logic?: string, rules?: any[] },
 *   onChange: (next: { logic: string, rules: any[] }) => void,
 *   disabled?: boolean,
 *   fieldMeta?: Array<{ value: string, label: string, kind: string, operators: { storage: string, label: string }[] }>,
 *   logicOptions?: Array<{ value: string, label: string }>,
 *   templates?: Array<{ id: string, label: string, conditions: { logic: string, rules: any[] } }>,
 * }} props
 */
export default function RegistryConditionsBuilder({
  value,
  onChange,
  disabled,
  fieldMeta = [],
  logicOptions = [
    { value: 'ALL', label: 'All rules must match (AND)' },
    { value: 'ANY', label: 'Any rule may match (OR)' },
  ],
  templates = [],
}) {
  const cond = useMemo(() => normalizeConditions(value), [value]);

  const setLogic = (logic) => {
    onChange({ ...cond, logic });
  };

  const setRules = (rules) => {
    onChange({ ...cond, rules });
  };

  const metaByField = useMemo(() => {
    const m = new Map();
    (fieldMeta || []).forEach((f) => m.set(f.value, f));
    return m;
  }, [fieldMeta]);

  const opsForRow = (field) => {
    const meta = metaByField.get(field);
    return meta?.operators || [];
  };

  const updateRule = (idx, patch) => {
    const next = cond.rules.map((r, j) => {
      if (j !== idx) return r;
      let merged = { ...r, ...patch };
      if (merged.op === 'true' || merged.op === 'false') {
        const { value: _drop, ...rest } = merged;
        merged = rest;
      }
      return merged;
    });
    setRules(next);
  };

  const addRule = () => {
    const fm = fieldMeta[0];
    if (!fm?.value) return;
    const firstOp = fm.operators?.[0]?.storage || 'true';
    const row = { field: fm.value, op: firstOp };
    if (firstOp !== 'true' && firstOp !== 'false') {
      if (fm.kind === 'boolean') row.value = true;
      else if (fm.kind === 'number') row.value = 0;
      else row.value = '';
    }
    setRules([...cond.rules, row]);
  };

  const removeRule = (idx) => {
    setRules(cond.rules.filter((_, j) => j !== idx));
  };

  const applyTemplate = (tpl) => {
    if (!tpl?.conditions) return;
    onChange(normalizeConditions(tpl.conditions));
  };

  const summary = humanSummaryRegistryConditions(cond);

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-600">
        Rules use the same <span className="font-mono">conditions.logic</span> and{' '}
        <span className="font-mono">conditions.rules[]</span> JSON shape as production validation — only approved fields
        and operators are listed here.
      </p>

      <div className="rounded-md border border-slate-200 bg-slate-50/90 px-3 py-2 text-xs text-slate-900 whitespace-pre-wrap">
        <span className="font-semibold text-slate-800">Applicability summary</span>
        <div className="mt-1 text-slate-800">{summary}</div>
      </div>

      {templates.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-gray-600">Quick templates:</span>
          {templates.map((t) => (
            <Button key={t.id} type="button" variant="outline" size="sm" disabled={disabled} onClick={() => applyTemplate(t)}>
              {t.label}
            </Button>
          ))}
        </div>
      )}

      <label className="block text-xs">
        <span className="text-gray-600">Combine rules using</span>
        <select
          className="mt-1 w-full max-w-md border border-gray-200 rounded-md px-2 py-1.5 text-sm bg-white"
          value={cond.logic}
          onChange={(e) => setLogic(e.target.value)}
          disabled={disabled}
        >
          {logicOptions.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      {!cond.rules.length ? (
        <p className="text-xs text-gray-500 italic">No rules yet — this requirement applies to all properties (subject to jurisdiction and planner).</p>
      ) : null}

      <div className="space-y-2">
        {cond.rules.map((row, i) => {
          const field = row.field || '';
          const op = row.op || '';
          const ops = opsForRow(field);
          const meta = metaByField.get(field);
          const kind = meta?.kind || 'boolean';
          const unary = op === 'true' || op === 'false';

          return (
            <div
              key={`${i}-${field}-${op}`}
              className="border border-gray-200 rounded-lg p-3 grid grid-cols-1 md:grid-cols-12 gap-2 bg-white items-end"
            >
              <label className="md:col-span-3 text-xs">
                <span className="text-gray-500 block mb-1">Field</span>
                <select
                  className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                  value={field}
                  onChange={(e) => {
                    const nf = e.target.value;
                    const nm = metaByField.get(nf);
                    const no = nm?.operators?.[0]?.storage || 'true';
                    const nextRow = { field: nf, op: no };
                    if (no === 'true' || no === 'false') {
                      /* omit value */
                    } else if (nm?.kind === 'boolean') nextRow.value = true;
                    else if (nm?.kind === 'number') nextRow.value = 0;
                    else if (no === 'in' || no === 'not_in') nextRow.value = [];
                    else nextRow.value = '';
                    updateRule(i, nextRow);
                  }}
                  disabled={disabled}
                >
                  <option value="">— Select field —</option>
                  {fieldMeta.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label} ({f.value})
                    </option>
                  ))}
                </select>
              </label>
              <label className="md:col-span-3 text-xs">
                <span className="text-gray-500 block mb-1">Operator</span>
                <select
                  className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                  value={op}
                  onChange={(e) => {
                    const no = e.target.value;
                    if (no === 'true' || no === 'false') {
                      updateRule(i, { field, op: no });
                    } else if (no === 'in' || no === 'not_in') {
                      updateRule(i, { op: no, value: Array.isArray(row.value) ? row.value : [] });
                    } else if (kind === 'boolean') {
                      updateRule(i, { op: no, value: true });
                    } else if (kind === 'number') {
                      updateRule(i, { op: no, value: Number(row.value) || 0 });
                    } else {
                      updateRule(i, { op: no, value: row.value != null ? String(row.value) : '' });
                    }
                  }}
                  disabled={disabled || !field}
                >
                  <option value="">—</option>
                  {ops.map((o) => (
                    <option key={o.storage} value={o.storage}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="md:col-span-5 text-xs">
                {!field || unary ? (
                  <span className="text-gray-400 block py-2">No value needed</span>
                ) : kind === 'boolean' && (op === '==' || op === '!=') ? (
                  <label>
                    <span className="text-gray-500 block mb-1">Value</span>
                    <select
                      className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                      value={row.value === false ? 'false' : 'true'}
                      onChange={(e) => updateRule(i, { value: e.target.value === 'true' })}
                      disabled={disabled}
                    >
                      <option value="true">Yes (true)</option>
                      <option value="false">No (false)</option>
                    </select>
                  </label>
                ) : kind === 'number' ? (
                  <label>
                    <span className="text-gray-500 block mb-1">Value</span>
                    <input
                      type="number"
                      className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                      value={row.value != null && row.value !== '' ? row.value : ''}
                      onChange={(e) => updateRule(i, { value: e.target.value === '' ? '' : Number(e.target.value) })}
                      disabled={disabled}
                    />
                  </label>
                ) : op === 'in' || op === 'not_in' ? (
                  <label>
                    <span className="text-gray-500 block mb-1">Values (one per line)</span>
                    <textarea
                      className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm font-mono"
                      rows={3}
                      value={Array.isArray(row.value) ? row.value.join('\n') : ''}
                      onChange={(e) =>
                        updateRule(i, {
                          value: e.target.value
                            .split(/\r?\n/)
                            .map((s) => s.trim())
                            .filter(Boolean),
                        })
                      }
                      disabled={disabled}
                    />
                  </label>
                ) : (
                  <label>
                    <span className="text-gray-500 block mb-1">Value</span>
                    <input
                      className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
                      value={row.value != null ? String(row.value) : ''}
                      onChange={(e) => updateRule(i, { value: e.target.value })}
                      disabled={disabled}
                    />
                  </label>
                )}
              </div>
              <div className="md:col-span-1 flex md:justify-end">
                <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => removeRule(i)}>
                  Remove
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      <Button type="button" size="sm" variant="secondary" onClick={addRule} disabled={disabled || !fieldMeta.length}>
        Add rule
      </Button>
    </div>
  );
}
