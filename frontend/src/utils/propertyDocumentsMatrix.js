/**
 * Single source of truth for property Compliance ↔ Documents matrix behaviour:
 * missing-document detection, criticality ordering, and shared sorts.
 */
import { normalizeRequirementCode, requirementTitleFromRow } from '../domain/presentDomain';

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
 * Presentation-only urgency tier for Needs Attention triage (not scoring authority).
 * Tier 1 — statutory / high-impact blockers; Tier 2 — operational compliance workflows; Tier 3 — supporting evidence.
 */
export function requirementNeedsAttentionUrgencyTier(r) {
  const code = normalizeRequirementCode(String(r?.requirement_code || r?.requirement_type || r?.canonical_code || ''));
  const tier1 = new Set([
    'gas_safety',
    'eicr',
    'epc',
    'hmo_license',
    'property_licence',
    'selective_license',
    'landlord_registration',
    'scotland_landlord_registration',
    'deposit_pi',
    'deposit_prescribed_info',
    'tenancy_deposit_protection',
    'right_to_rent',
    'right_to_rent_checks',
    'rent_smart_wales',
    'landlord_registration_ni',
  ]);
  /** PAT and similar supporting uploads; occupation/contract proofs stay tier 2 (default). */
  const tier3 = new Set(['portable_appliance_test']);
  if (tier1.has(code)) return 1;
  if (tier3.has(code)) return 3;
  return 2;
}

/** True when row should not appear in Needs Attention (valid/compliant with no follow-up or incomplete evidence). */
export function isRequirementExcludedFromNeedsAttention(r) {
  const s = String(r?.status || '').toUpperCase();
  if (['NOT_APPLICABLE', 'NOT_REQUIRED', 'WAIVED'].includes(s)) return true;
  const followUpDue = s === 'PENDING' && !!r?.evidence_doc_id;
  const wf = String(r?.workflow_class || '').toUpperCase();
  const evidenceSummary = String(r?.evidence_completeness?.summary_label || '').toUpperCase();
  const incompleteRequiredEvidence =
    wf === 'MULTI_EVIDENCE' || (evidenceSummary && evidenceSummary !== 'COMPLETE');
  if (['COMPLIANT', 'VALID'].includes(s)) {
    if (followUpDue || incompleteRequiredEvidence) return false;
    return true;
  }
  return false;
}

/**
 * Needs-attention priority subset (not the full register).
 * Ordering: urgency tier (1→2→3), then overdue / expired / high-risk missing / expiring / follow-up / incomplete / missing.
 */
export function buildNeedsAttentionSubset(requirements, rowExpiry, cap = 8) {
  const exp = (r) => rowExpiry(r) || '';
  const filtered = (Array.isArray(requirements) ? requirements : []).filter((r) => {
    if (isRequirementExcludedFromNeedsAttention(r)) return false;
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
  const ordered = [...filtered].sort(
    (a, b) =>
      requirementNeedsAttentionUrgencyTier(a) - requirementNeedsAttentionUrgencyTier(b) ||
      requirementAttentionStatusRank(a) - requirementAttentionStatusRank(b) ||
      requirementCriticalityRank(a) - requirementCriticalityRank(b) ||
      String(exp(a)).localeCompare(String(exp(b))),
  );
  const normalizedCap = Math.max(1, Number(cap || 8));
  const items = ordered.slice(0, normalizedCap);
  return {
    items,
    total: ordered.length,
    overflowCount: Math.max(0, ordered.length - items.length),
  };
}
