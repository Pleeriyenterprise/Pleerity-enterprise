import { JURISDICTION_OPTIONS } from './jurisdictionComplianceCopy';
import { normalizeUkPostcode } from './ukPostcode';

/**
 * Map postcodes.io country to portfolio jurisdiction label when unambiguous.
 * @param {Record<string, unknown> | null | undefined} lookupData
 * @returns {string}
 */
export function jurisdictionFromPostcodeLookup(lookupData) {
  const country = String(lookupData?.country || '').trim();
  if (country && JURISDICTION_OPTIONS.includes(country)) {
    return country;
  }
  return '';
}

/**
 * Build canonical postcode from autocomplete suggestion (intake parity).
 * @param {Record<string, unknown> | null | undefined} suggestion
 * @returns {string}
 */
export function postcodeFromSuggestion(suggestion) {
  const rawPc = String(suggestion?.postcode || '').trim();
  const out = String(suggestion?.outcode || '').trim();
  const inn = String(suggestion?.incode || '').trim();
  const combined = rawPc || (out && inn ? `${out} ${inn}`.trim() : out || '');
  return normalizeUkPostcode(combined);
}

/**
 * Derive field updates after a successful postcode lookup.
 * Street lines are not provided by postcodes.io — user enters manually (intake parity).
 *
 * @param {Record<string, unknown>} lookupData
 * @param {{ postcode?: string, city?: string, jurisdiction?: string }} current
 * @param {{ fillOnlyEmpty?: boolean }} [options]
 * @returns {{ postcode?: string, city?: string, jurisdiction?: string }}
 */
export function applyPostcodeLookupResult(lookupData, current = {}, options = {}) {
  const { fillOnlyEmpty = true } = options;
  const updates = {};
  const canonical = normalizeUkPostcode(String(lookupData?.postcode || current.postcode || ''));
  if (canonical) {
    updates.postcode = canonical;
  }
  const suggestedCity = String(lookupData?.suggested_city || '').trim();
  if (suggestedCity && (!fillOnlyEmpty || !String(current.city || '').trim())) {
    updates.city = suggestedCity;
  }
  const suggestedJurisdiction = jurisdictionFromPostcodeLookup(lookupData);
  if (suggestedJurisdiction && (!fillOnlyEmpty || !String(current.jurisdiction || '').trim())) {
    updates.jurisdiction = suggestedJurisdiction;
  }
  return updates;
}
