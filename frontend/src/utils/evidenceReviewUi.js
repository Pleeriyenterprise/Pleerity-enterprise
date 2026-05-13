export function effectiveEvidenceReviewState(doc = {}) {
  const direct = String(doc?.evidence_review_state || '').trim().toUpperCase();
  if (direct) return direct;
  const tier = String(doc?.assurance_tier || '').trim().toUpperCase();
  // Prevent misleading "Uploaded" when assurance tier already reflects external verification but state lagged.
  if (tier === 'EXTERNALLY_VERIFIED') return 'VERIFIED';
  const legacy = String(doc?.status || '').trim().toUpperCase();
  if (legacy === 'VERIFIED') return 'ACCEPTED_UNVERIFIED';
  if (legacy === 'REJECTED') return 'REJECTED';
  if (legacy === 'EXPIRED') return 'EXPIRED';
  return 'UPLOADED';
}

export function effectiveAssuranceTier(doc = {}) {
  const direct = String(doc?.assurance_tier || '').trim().toUpperCase();
  if (direct) return direct;
  const legacy = String(doc?.status || '').trim().toUpperCase();
  if (legacy === 'VERIFIED') return 'HUMAN_ACCEPTED';
  if (legacy === 'REJECTED') return 'REJECTED';
  if (legacy === 'EXPIRED') return 'SYSTEM_EXPIRED';
  return 'USER_UPLOADED';
}

export function reviewStateLabel(state) {
  const s = String(state || '').toUpperCase();
  const labels = {
    UPLOADED: 'Uploaded',
    UNDER_REVIEW: 'Under review',
    NEEDS_INFORMATION: 'Needs information',
    REJECTED: 'Rejected',
    ACCEPTED_UNVERIFIED: 'Accepted on file (not externally verified)',
    VERIFIED: 'Verified',
    EXPIRED: 'Expired',
    SUPERSEDED: 'Superseded',
  };
  return labels[s] || (s || 'Unknown');
}

export function assuranceTierLabel(tier) {
  const t = String(tier || '').toUpperCase();
  const labels = {
    NONE: 'No assurance',
    USER_UPLOADED: 'User uploaded',
    HUMAN_ACCEPTED: 'Human accepted',
    EXTERNALLY_VERIFIED: 'Externally verified',
    SYSTEM_EXPIRED: 'Expired',
    REJECTED: 'Rejected',
  };
  return labels[t] || (t || 'Unknown');
}

export function clientFacingVerificationLabel(doc = {}) {
  const tier = effectiveAssuranceTier(doc);
  if (tier === 'EXTERNALLY_VERIFIED') return 'Externally verified';
  const st = effectiveEvidenceReviewState(doc);
  if (st === 'ACCEPTED_UNVERIFIED') return 'Accepted on file (not externally verified)';
  if (st === 'VERIFIED') return 'Verified';
  if (st === 'REJECTED') return 'Rejected';
  if (st === 'EXPIRED') return 'Expired';
  if (st === 'NEEDS_INFORMATION') return 'Needs information';
  if (st === 'UNDER_REVIEW') return 'Under review';
  if (st === 'SUPERSEDED') return 'Superseded';
  return 'Uploaded';
}

export function isPositiveEvidenceState(doc = {}) {
  const st = effectiveEvidenceReviewState(doc);
  return st === 'ACCEPTED_UNVERIFIED' || st === 'VERIFIED';
}

/**
 * True when a separate “verification / assurance” pill would repeat the same
 * user-facing phrase as the primary evidence row label (Documents row, property tables).
 */
export function clientVerificationLabelRedundantWithPrimary(doc, primaryRowLabel) {
  const a = String(primaryRowLabel || '').trim().toLowerCase();
  const b = String(clientFacingVerificationLabel(doc) || '').trim().toLowerCase();
  return Boolean(a) && Boolean(b) && a === b;
}

