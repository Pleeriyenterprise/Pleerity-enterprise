/**
 * Single source of truth for property Compliance ↔ Documents matrix behaviour:
 * missing-document detection, criticality ordering, and shared sorts.
 */
import { requirementLabel } from '../domain/presentDomain';

/**
 * True when a file still needs to be supplied (not awaiting verification on an uploaded file).
 * PENDING + linked document = verification path, excluded from “missing document” counts/filters.
 */
export function isRequirementMissingDocument(r) {
  const s = (r?.status || '').toUpperCase();
  if (s === 'MISSING' || s === 'MISSING_EVIDENCE') return true;
  if (s === 'PENDING') return !r?.evidence_doc_id;
  return false;
}

export function requirementCriticalityRank(r) {
  const c = (r?.criticality || '').toUpperCase();
  if (c === 'HIGH') return 0;
  if (c === 'MED' || c === 'MEDIUM') return 1;
  return 2;
}

function defaultRowTitle(r) {
  return (
    r?.title ||
    (r?.requirement_code || r?.requirement_type ? requirementLabel(r.requirement_code || r.requirement_type) : null) ||
    r?.description ||
    r?.name ||
    '—'
  );
}

/**
 * @param {object[]} requirements
 * @param {function(object): string} [titleFn] row title for alphabetical tie-break
 */
export function sortRequirementsCriticalityThenTitle(requirements, titleFn = defaultRowTitle) {
  return [...requirements].sort(
    (a, b) =>
      requirementCriticalityRank(a) - requirementCriticalityRank(b) || String(titleFn(a)).localeCompare(String(titleFn(b))),
  );
}

/** Obligations with no linked document (PENDING / MISSING), highest criticality first. */
export function listRequirementsMissingDocumentsSorted(requirements) {
  return sortRequirementsCriticalityThenTitle(requirements.filter(isRequirementMissingDocument));
}

/**
 * Operating hub ordering: time-critical first, then gaps (no document), then verification queue,
 * then expiring — so high-impact missing documents surface before lower-urgency expiry-only items.
 */
export function requirementAttentionStatusRank(r) {
  const u = String(r?.status || '').toUpperCase();
  if (u === 'OVERDUE' || u === 'EXPIRED') return 0;
  if (isRequirementMissingDocument(r)) return 1;
  if (u === 'PENDING' && r?.evidence_doc_id) return 2;
  if (u === 'EXPIRING_SOON') return 3;
  return 9;
}

export function sortRequirementsAttentionOrder(requirements, rowExpiry) {
  const exp = (r) => rowExpiry(r) || '';
  return [...requirements].sort(
    (a, b) =>
      requirementAttentionStatusRank(a) - requirementAttentionStatusRank(b) ||
      requirementCriticalityRank(a) - requirementCriticalityRank(b) ||
      String(exp(a)).localeCompare(String(exp(b))),
  );
}
