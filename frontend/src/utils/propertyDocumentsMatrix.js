/**
 * Single source of truth for property Compliance ↔ Documents matrix behaviour:
 * missing-document detection, criticality ordering, and shared sorts.
 */
import { normalizeRequirementCode, requirementTitleFromRow } from '../domain/presentDomain';
import { resolveClientRequirementLifecycle } from './clientRequirementLifecycle';
import { isMultiEvidenceStyleWorkflow } from './workflowSemantics';

/** Same predicate as {@link projectResolvedRequirementSemantics}.is_multi_evidence_style — avoids resolver churn in hot loops. */
function incompleteMultiEvidenceFamily(r) {
  return isMultiEvidenceStyleWorkflow(r?.workflow_class);
}

/**
 * True when a file still needs to be supplied (not awaiting verification on an uploaded file).
 * Uses backend satisfaction truth when present; legacy fallback for stale payloads.
 */
export function isRequirementMissingDocument(r) {
  if (r?.missing_required_document === true) return true;
  if (r?.missing_required_document === false || r?.requirement_satisfied === true) return false;
  if (r?.document_upload_required === false) return false;
  const s = (r?.status || '').toUpperCase();
  if (s === 'MISSING' || s === 'MISSING_EVIDENCE') return true;
  if (s === 'PENDING') return !(r?.evidence_doc_id || String(r?.document_id || '').trim());
  return false;
}

/** Requirements satisfied without an uploaded document (declarations / self-cert). */
export function isRequirementSatisfiedWithoutUploadedDocument(r) {
  if (r?.requirement_satisfied === true && r?.missing_required_document === false) {
    return !(r?.evidence_doc_id || String(r?.document_id || '').trim());
  }
  if (r?.satisfaction_source && ['accepted_declaration', 'self_certified_record', 'org_review'].includes(r.satisfaction_source)) {
    return true;
  }
  const { state } = resolveClientRequirementLifecycle(r);
  if (state === 'SATISFIED_UNVERIFIED' || state === 'VERIFIED') {
    return !isRequirementMissingDocument(r) && !(r?.evidence_doc_id || String(r?.document_id || '').trim());
  }
  return false;
}

/** True when landlord action is still required (aligned with backend attention eligibility). */
export function isRequirementActionRequired(r) {
  if (r?.requirement_attention_eligible === true) return true;
  if (r?.requirement_attention_eligible === false || r?.requirement_satisfied === true) return false;
  return resolveClientRequirementLifecycle(r).state === 'ACTION_REQUIRED';
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
  const evidenceSummary = String(r?.evidence_completeness?.summary_label || '').toUpperCase();
  const incompleteRequiredEvidence =
    incompleteMultiEvidenceFamily(r) || (evidenceSummary && evidenceSummary !== 'COMPLETE');
  if (u === 'OVERDUE') return 0;
  if (u === 'EXPIRED' || u === 'FAILED') return 1;
  if (isHighRiskMissingEvidence) return 2;
  if (u === 'EXPIRING_SOON') return 3;
  if (u === 'PENDING' && (r?.evidence_doc_id || String(r?.document_id || '').trim())) return 4;
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
  if (r?.requirement_attention_eligible === false) return true;
  if (r?.requirement_satisfied === true && r?.requirement_attention_eligible !== true) return true;
  const st = String(r?.status || '').toUpperCase();
  if (st === 'EXPIRING_SOON') return false;
  const { state } = resolveClientRequirementLifecycle(r);
  if (state === 'PENDING_REVIEW' || state === 'NOT_APPLICABLE') return true;
  if (state === 'VERIFIED' || state === 'SATISFIED_UNVERIFIED') {
    const followUpDue = st === 'PENDING' && !!(r?.evidence_doc_id || String(r?.document_id || '').trim());
    const evidenceSummary = String(r?.evidence_completeness?.summary_label || '').toUpperCase();
    const incompleteRequiredEvidence =
      incompleteMultiEvidenceFamily(r) || (evidenceSummary && evidenceSummary !== 'COMPLETE');
    if (followUpDue || incompleteRequiredEvidence) return false;
    return true;
  }
  const followUpDue = st === 'PENDING' && !!(r?.evidence_doc_id || String(r?.document_id || '').trim());
  const evidenceSummary = String(r?.evidence_completeness?.summary_label || '').toUpperCase();
  const incompleteRequiredEvidence =
    incompleteMultiEvidenceFamily(r) || (evidenceSummary && evidenceSummary !== 'COMPLETE');
  if (['NOT_APPLICABLE', 'NOT_REQUIRED', 'WAIVED'].includes(st)) return true;
  if (['COMPLIANT', 'VALID'].includes(st)) {
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
    const lc = resolveClientRequirementLifecycle(r).state;
    const followUpDue =
      s === 'PENDING' &&
      !!(r?.evidence_doc_id || String(r?.document_id || '').trim()) &&
      lc === 'ACTION_REQUIRED';
    const evidenceSummary = String(r?.evidence_completeness?.summary_label || '').toUpperCase();
    const incompleteRequiredEvidence =
      incompleteMultiEvidenceFamily(r) || (evidenceSummary && evidenceSummary !== 'COMPLETE');
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
