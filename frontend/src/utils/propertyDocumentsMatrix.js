/**
 * Single source of truth for property Compliance ↔ Documents matrix behaviour:
 * missing-document detection, criticality ordering, and shared sorts.
 */
import { requirementTitleFromRow } from '../domain/presentDomain';

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
  return requirementTitleFromRow(r, 'detail');
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
  const isHighRiskMissingEvidence = isRequirementMissingDocument(r) && requirementCriticalityRank(r) === 0;
  const wf = String(r?.workflow_class || '').toUpperCase();
  const evidenceSummary = String(r?.evidence_completeness?.summary_label || '').toUpperCase();
  const incompleteRequiredEvidence =
    wf === 'MULTI_EVIDENCE' || (evidenceSummary && evidenceSummary !== 'COMPLETE');
  if (u === 'OVERDUE') return 0;
  if (u === 'EXPIRED' || u === 'FAILED') return 1;
  if (isHighRiskMissingEvidence) return 2;
  if (u === 'EXPIRING_SOON') return 3;
  if (u === 'PENDING' && r?.evidence_doc_id) return 4;
  if (incompleteRequiredEvidence) return 5;
  if (isRequirementMissingDocument(r)) return 6;
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

/**
 * Needs-attention priority subset (not the full register).
 * Order: overdue, expired, high-risk missing evidence, expiring soon,
 * follow-up due, incomplete required evidence, then remaining missing evidence.
 */
export function buildNeedsAttentionSubset(requirements, rowExpiry, cap = 8) {
  const filtered = (Array.isArray(requirements) ? requirements : []).filter((r) => {
    const s = String(r?.status || '').toUpperCase();
    const followUpDue = s === 'PENDING' && !!r?.evidence_doc_id;
    const wf = String(r?.workflow_class || '').toUpperCase();
    const evidenceSummary = String(r?.evidence_completeness?.summary_label || '').toUpperCase();
    const incompleteRequiredEvidence =
      wf === 'MULTI_EVIDENCE' || (evidenceSummary && evidenceSummary !== 'COMPLETE');
    return (
      s === 'OVERDUE' ||
      s === 'EXPIRED' ||
      s === 'FAILED' ||
      s === 'EXPIRING_SOON' ||
      isRequirementMissingDocument(r) ||
      followUpDue ||
      incompleteRequiredEvidence
    );
  });
  const ordered = sortRequirementsAttentionOrder(filtered, rowExpiry);
  const normalizedCap = Math.max(1, Number(cap || 8));
  const items = ordered.slice(0, normalizedCap);
  return {
    items,
    total: ordered.length,
    overflowCount: Math.max(0, ordered.length - items.length),
  };
}
