/**
 * Plain-English summary for registry draft conditions.
 * Keep aligned with ``human_summary_registry_conditions`` in compliance_registry_conditions.py.
 */
const FIELD_LABELS = {
  is_hmo: 'Is HMO',
  has_gas_supply: 'Has gas supply',
  tenancy_active: 'Tenancy active',
  furnished: 'Furnished',
  deposit_taken: 'Deposit taken',
  has_communal_areas: 'Has communal areas',
  local_authority: 'Local authority',
  property_type: 'Property type',
  building_age_years: 'Building age (years)',
  licence_required: 'Licence required',
  cert_gas_safety: 'Gas safety certificate',
  cert_licence: 'Licence certificate',
  licence_type: 'Licence type',
};

function label(field) {
  return FIELD_LABELS[field] || String(field || '').replace(/_/g, ' ');
}

function fmt(val) {
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  if (val == null) return '—';
  if (Array.isArray(val)) return val.filter((x) => x != null && String(x).trim() !== '').join(', ');
  return String(val);
}

export function humanSummaryRegistryConditions(cond) {
  if (!cond || typeof cond !== 'object') return '';
  const rules = Array.isArray(cond.rules) ? cond.rules : [];
  if (!rules.length) return 'Applies to all properties (no rules).';
  const logic = String(cond.logic || 'ALL').toUpperCase();
  const joiner = logic === 'ANY' ? 'any of the following are true' : 'all of the following are true';
  const lines = [];
  for (const r of rules) {
    if (!r || typeof r !== 'object') continue;
    const f = String(r.field || '').trim();
    if (!f) continue;
    const op = String(r.op || '').trim();
    const val = r.value;
    const lb = label(f);
    if (op === 'true') lines.push(`${lb} is Yes`);
    else if (op === 'false') lines.push(`${lb} is No`);
    else if (op === '==') lines.push(`${lb} equals ${fmt(val)}`);
    else if (op === '!=') lines.push(`${lb} is not ${fmt(val)}`);
    else if (op === 'in') lines.push(`${lb} is one of: ${fmt(val)}`);
    else if (op === 'not_in') lines.push(`${lb} is not one of: ${fmt(val)}`);
    else if (op === 'gt') lines.push(`${lb} is greater than ${fmt(val)}`);
    else if (op === 'lt') lines.push(`${lb} is less than ${fmt(val)}`);
    else lines.push(`${lb} (${op})`);
  }
  if (!lines.length) return 'Applies to all properties (no rules).';
  return `Applies when ${joiner}:\n${lines.map((x) => `  • ${x}`).join('\n')}`;
}
