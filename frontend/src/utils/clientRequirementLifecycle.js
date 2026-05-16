/**
 * Canonical client requirement lifecycle — prefer API `client_lifecycle_*` fields
 * from `enrich_requirements_for_client`; fall back only when absent.
 */

/** @typedef {'ACTION_REQUIRED'|'PENDING_REVIEW'|'SATISFIED_UNVERIFIED'|'VERIFIED'|'NOT_APPLICABLE'} ClientLifecycleState */

const CLIENT_LIFECYCLE_SET = new Set([
  'ACTION_REQUIRED',
  'PENDING_REVIEW',
  'SATISFIED_UNVERIFIED',
  'VERIFIED',
  'NOT_APPLICABLE',
]);

const DEFAULT_LABELS = {
  ACTION_REQUIRED: 'Action required',
  PENDING_REVIEW: 'Awaiting review',
  SATISFIED_UNVERIFIED: 'Evidence recorded',
  VERIFIED: 'Verified',
  NOT_APPLICABLE: 'Not applicable',
};

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
function eaState(row) {
  const ea = row?.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  return String(ea?.state || '').trim().toUpperCase();
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {{ state: ClientLifecycleState, label: string, reasonCodes: string[], source: 'api'|'fallback' }}
 */
export function resolveClientRequirementLifecycle(row) {
  const raw = String(row?.client_lifecycle_state || '').trim().toUpperCase();
  if (raw && CLIENT_LIFECYCLE_SET.has(raw)) {
    const label =
      typeof row?.client_lifecycle_label === 'string' && row.client_lifecycle_label.trim()
        ? row.client_lifecycle_label.trim()
        : DEFAULT_LABELS[raw] || DEFAULT_LABELS.ACTION_REQUIRED;
    const reasonCodes = Array.isArray(row?.client_lifecycle_reason_codes)
      ? row.client_lifecycle_reason_codes.map((x) => String(x))
      : [];
    return { state: /** @type {ClientLifecycleState} */ (raw), label, reasonCodes, source: 'api' };
  }
  return fallbackLegacyLifecycle(row);
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
function fallbackLegacyLifecycle(row) {
  const r = row && typeof row === 'object' ? row : {};
  const app = String(r.applicability || '').toUpperCase();
  const st = String(r.status || '').toUpperCase();
  const ev = String(r.evidence_state || '').toUpperCase();
  const ea = eaState(r);
  if (app === 'NOT_REQUIRED' || st === 'NOT_REQUIRED' || st === 'NOT_APPLICABLE' || ea === 'NOT_REQUIRED') {
    return { state: 'NOT_APPLICABLE', label: DEFAULT_LABELS.NOT_APPLICABLE, reasonCodes: ['FALLBACK_NOT_APPLICABLE'], source: 'fallback' };
  }
  if (ea === 'PENDING_ADMIN_REVIEW') {
    return {
      state: 'PENDING_REVIEW',
      label: DEFAULT_LABELS.PENDING_REVIEW,
      reasonCodes: ['FALLBACK_EA_PENDING_ADMIN_REVIEW'],
      source: 'fallback',
    };
  }
  if (
    st === 'OVERDUE' ||
    st === 'MISSING' ||
    st === 'MISSING_EVIDENCE' ||
    ev === 'MISSING' ||
    ev === 'MISMATCH_FLAGGED' ||
    ev === 'AWAITING_USER_CONFIRM'
  ) {
    return { state: 'ACTION_REQUIRED', label: DEFAULT_LABELS.ACTION_REQUIRED, reasonCodes: ['FALLBACK_ACTION_HEURISTIC'], source: 'fallback' };
  }
  if (ea === 'VERIFIED_CURRENT' || (st === 'COMPLIANT' && ev === 'VERIFIED')) {
    return { state: 'VERIFIED', label: DEFAULT_LABELS.VERIFIED, reasonCodes: ['FALLBACK_VERIFIED_HEURISTIC'], source: 'fallback' };
  }
  if (st === 'PENDING' && (r.evidence_doc_id || String(r.document_id || '').trim())) {
    return { state: 'PENDING_REVIEW', label: DEFAULT_LABELS.PENDING_REVIEW, reasonCodes: ['FALLBACK_PENDING_WITH_DOC'], source: 'fallback' };
  }
  if (st === 'COMPLIANT' || st === 'VALID' || st === 'EXPIRING_SOON') {
    return {
      state: st === 'EXPIRING_SOON' ? 'VERIFIED' : 'SATISFIED_UNVERIFIED',
      label: st === 'EXPIRING_SOON' ? 'Expiring soon' : DEFAULT_LABELS.SATISFIED_UNVERIFIED,
      reasonCodes: ['FALLBACK_SATISFIED_HEURISTIC'],
      source: 'fallback',
    };
  }
  return { state: 'ACTION_REQUIRED', label: DEFAULT_LABELS.ACTION_REQUIRED, reasonCodes: ['FALLBACK_DEFAULT'], source: 'fallback' };
}

/**
 * @param {Record<string, unknown>|null|undefined} req
 */
export function isRequirementNotApplicableLifecycle(req) {
  return resolveClientRequirementLifecycle(req).state === 'NOT_APPLICABLE';
}

/**
 * Tracked portfolio rows (excludes not-applicable lifecycle). Same class/applicability gates as before.
 * @param {Record<string, unknown>|null|undefined} req
 */
export function isRequirementIncludedInAttentionViews(req) {
  if (!req || typeof req !== 'object') return false;
  if (isRequirementNotApplicableLifecycle(req)) return false;
  if (req.is_tracked === false || req.tracked === false) return false;
  const cls = String(req.compliance_requirement_class || req.requirement_class || '').toUpperCase();
  if (cls === 'OBLIGATION' || cls === 'SYSTEM') return false;
  if (cls && cls !== 'DOCUMENT' && cls !== 'JOB') return false;
  const app = String(req.applicability || '').toUpperCase().trim();
  if (app === 'NOT_REQUIRED') return false;
  const st = String(req.status || '').toUpperCase();
  if (st === 'NOT_REQUIRED') return false;
  return true;
}

/**
 * Urgent user-action attention (red / “do this next” queues).
 * @param {Record<string, unknown>|null|undefined} req
 */
export function isRequirementUrgentActionAttention(req) {
  return resolveClientRequirementLifecycle(req).state === 'ACTION_REQUIRED';
}

/**
 * Internal review queue — not counted as missing evidence.
 * @param {Record<string, unknown>|null|undefined} req
 */
export function isRequirementPendingReviewAttention(req) {
  return resolveClientRequirementLifecycle(req).state === 'PENDING_REVIEW';
}
