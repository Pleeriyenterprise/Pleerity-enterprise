/**
 * Single canonical source for "why it matters" copy on client requirement surfaces
 * (Property Compliance inline, Requirement Intelligence modal). Do not parallel this with ad-hoc API explanations.
 */

function normJurisdictionKey(j) {
  return String(j || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_');
}

/**
 * @param {Record<string, unknown>|null|undefined} byPublished
 * @param {string|null|undefined} propertyJurisdiction
 * @returns {{ short: string, long: string, matchedKey: string } | null}
 */
export function resolveWhyItMattersFromJurisdictionMap(byPublished, propertyJurisdiction) {
  if (!byPublished || typeof byPublished !== 'object' || !propertyJurisdiction) return null;
  const want = normJurisdictionKey(propertyJurisdiction);
  if (!want) return null;
  for (const [k, v] of Object.entries(byPublished)) {
    if (!k || v == null) continue;
    if (normJurisdictionKey(k) !== want) continue;
    if (typeof v === 'string') {
      const s = v.trim();
      return s ? { short: s, long: '', matchedKey: k } : null;
    }
    if (typeof v === 'object') {
      const short =
        String(v.why_it_matters_short || v.short || v.summary || '').trim() ||
        String(v.why_it_matters || '').trim();
      const long = String(v.why_it_matters_long || v.long || v.detail || '').trim();
      if (short || long) return { short: short || long, long: long && long !== short ? long : '', matchedKey: k };
    }
  }
  return null;
}

/**
 * One short line for matrix / urgent inline (same resolution order as modal body).
 * @param {Record<string, unknown>|null|undefined} merged
 */
export function pickCanonicalWhyItMattersShort(merged) {
  const w = pickWhyItMattersForDisplay(merged);
  if (!w) return '';
  const one = String(w.short || '').trim();
  if (one) return one;
  const two = String(w.long || '').trim();
  return two ? (two.length > 280 ? `${two.slice(0, 277)}…` : two) : '';
}

/**
 * @param {Record<string, unknown>|null|undefined} merged
 * @returns {{
 *   source: 'published_jurisdiction'|'published'|'generic',
 *   short: string,
 *   long: string,
 *   jurisdictionRulesLabel: string|null,
 * }}
 */
export function pickWhyItMattersForDisplay(merged) {
  if (!merged || typeof merged !== 'object') {
    return { source: 'generic', short: '', long: '', jurisdictionRulesLabel: null };
  }
  const meta = merged.registry_metadata && typeof merged.registry_metadata === 'object' ? merged.registry_metadata : {};
  const propJur = merged.property_jurisdiction || merged.jurisdiction || null;
  const byJur = meta.why_it_matters_by_jurisdiction_published;
  const jurResolved = resolveWhyItMattersFromJurisdictionMap(byJur, propJur);
  if (jurResolved && (jurResolved.short || jurResolved.long)) {
    return {
      source: 'published_jurisdiction',
      short: jurResolved.short,
      long: jurResolved.long,
      jurisdictionRulesLabel: propJur ? String(propJur).trim() : null,
    };
  }
  const pubShort = meta.why_it_matters_short_published;
  const pubLong = meta.why_it_matters_long_published;
  const hasPublished =
    (typeof pubShort === 'string' && pubShort.trim()) || (typeof pubLong === 'string' && pubLong.trim());
  if (hasPublished) {
    return {
      source: 'published',
      short: typeof pubShort === 'string' ? pubShort.trim() : '',
      long: typeof pubLong === 'string' ? pubLong.trim() : '',
      jurisdictionRulesLabel: null,
    };
  }
  const short = typeof merged.why_it_matters_short === 'string' ? merged.why_it_matters_short.trim() : '';
  const long = typeof merged.why_it_matters_long === 'string' ? merged.why_it_matters_long.trim() : '';
  return { source: 'generic', short, long, jurisdictionRulesLabel: null };
}
