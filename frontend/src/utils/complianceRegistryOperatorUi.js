/**
 * Human-readable copy for the Compliance Requirement Registry (admin) — operator UX,
 * not a second source of truth: canonical codes/keys still live on the draft object.
 */

/** @type {Record<string, string>} */
const REVIEW_FIELD_PATTERNS = {
  'jurisdiction.ni.enforcement_detail': 'Northern Ireland enforcement detail needs review',
  'jurisdiction.england_wales.notes': 'England & Wales notes need review',
  'jurisdiction.scotland.notes': 'Scotland-specific notes need review',
  'conditions.installation_age_bands': 'Installation age-band conditions need review',
  'conditions.energy_efficiency_tiers': 'Energy efficiency tier conditions need review',
  why_it_matters_short: '“Why it matters” short copy needs review (or replace placeholder autofill)',
};

const SCOPE_FRIENDLY = {
  DEFAULT: "Default (UK-wide baseline line — not “all regions by accident” unless jurisdictions list says so)",
  WALES: 'Wales / Cymru',
  SCOTLAND: 'Scotland',
  ENGLAND: 'England',
  NORTHERN_IRELAND: 'Northern Ireland',
};

/**
 * @param {string} raw
 * @returns {string}
 */
export function formatScopeKeyLabel(raw) {
  const k = String(raw || 'DEFAULT').trim() || 'DEFAULT';
  if (SCOPE_FRIENDLY[k]) return SCOPE_FRIENDLY[k];
  if (k === 'DEFAULT') return SCOPE_FRIENDLY.DEFAULT;
  return k.replace(/_/g, ' ');
}

/**
 * @param {string} key
 * @returns {string}
 */
export function formatReviewFieldLabel(key) {
  const s = String(key || '').trim();
  if (!s) return 'Review';
  if (REVIEW_FIELD_PATTERNS[s]) return REVIEW_FIELD_PATTERNS[s];
  if (s.includes('.')) {
    const last = s.split('.').pop() || s;
    const label = last.replace(/_/g, ' ');
    return `${label.replace(/^\w/, (c) => c.toUpperCase())} needs review (${s})`;
  }
  return s.replace(/_/g, ' ');
}

const REGION_PRETTY = {
  ENGLAND: 'England',
  WALES: 'Wales',
  SCOTLAND: 'Scotland',
  NORTHERN_IRELAND: 'Northern Ireland',
  ENGLAND_WALES: 'England & Wales',
  UK: 'United Kingdom',
};

/**
 * @param {string[]} regions
 * @returns {string}
 */
export function formatDisplayJurisdictions(regions) {
  if (!Array.isArray(regions) || !regions.length) return '—';
  return regions
    .map((r) => {
      const u = String(r).trim().toUpperCase();
      return REGION_PRETTY[u] || String(r);
    })
    .join(', ');
}

/**
 * @param {Record<string, unknown> | null} draft
 * @returns {string}
 */
export function buildEffectiveJurisdictionsSummary(draft) {
  if (!draft || typeof draft !== 'object') return '';
  const j = /** @type {any} */ (draft).jurisdiction;
  if (!j || typeof j !== 'object') return '';
  const dj = j.display_jurisdictions;
  if (!Array.isArray(dj) || !dj.length) {
    return 'No display regions are set on this draft — you cannot save/publish a client-visible requirement like this until regions are explicit.';
  }
  const sk = String(draft.scope_key || 'DEFAULT');
  const scopeLine = `Scope key: ${formatScopeKeyLabel(sk)} (planner/merge bucket; not the same as legal territory list).`;
  const regions = formatDisplayJurisdictions(dj);
  const note = j.scoring_jurisdiction_note ? ` Scoring note: ${j.scoring_jurisdiction_note}` : '';
  return `${scopeLine} Effective UK regions in client presentation for this line: ${regions}.${note}`;
}

/**
 * @param {string[]} displayRegions
 * @returns {boolean}
 */
export function displayRegionsCoverAllUK(displayRegions) {
  if (!Array.isArray(displayRegions)) return false;
  const u = new Set(
    displayRegions
      .map((r) =>
        String(r)
          .trim()
          .toUpperCase()
          .replace(/ /g, '_'),
      )
      .filter(Boolean),
  );
  return ['ENGLAND', 'WALES', 'SCOTLAND', 'NORTHERN_IRELAND'].every((k) => u.has(k));
}

/**
 * @param {Record<string, unknown>} row
 * @returns {{ label: string, intent: 'draft'|'review'|'ready'|'stale' }}
 */
export function registryListRowState(row) {
  const needs = Array.isArray(row?.governance?.needs_review_fields)
    ? row.governance.needs_review_fields.length
    : 0;
  if (needs) {
    return { label: 'Needs review', intent: 'review' };
  }
  return { label: 'Draft (editable)', intent: 'ready' };
}

/**
 * @param {Set<string> | null} liveKeys
 * @param {string} canonical
 * @param {string} scope
 * @returns {'none' | 'in_snapshot'}
 */
export function publishedLineStatusForRow(liveKeys, canonical, scope) {
  if (!liveKeys || !liveKeys.size) return 'none';
  const k = `${String(canonical || '').toUpperCase()}|${String(scope || 'DEFAULT').trim() || 'DEFAULT'}`;
  return liveKeys.has(k) ? 'in_snapshot' : 'none';
}

/**
 * @param {Record<string, unknown> | null} link
 * @param {string} region
 */
export function actionLinkAppliesToRegion(link, region) {
  const r = String(region || 'ENGLAND')
    .trim()
    .toUpperCase();
  const j = link?.jurisdictions;
  if (!Array.isArray(j) || !j.length) return false;
  return j
    .map((x) => String(x).trim().toUpperCase())
    .includes(r);
}
