/**
 * REPORTING-TRUTH-CONVERGENCE-PHASE-01 — aligned labels for requirement count surfaces.
 * Backend authority: GET /client/compliance-score → reporting_semantics
 */

export const REPORTING_SEMANTICS_LABELS = {
  tracked_requirement_count: {
    label: 'Tracked requirements',
    tooltip:
      'Items in scope on this page (registry attention view). May differ from score-tracked obligations on the dashboard.',
  },
  score_tracked_requirement_count: {
    label: 'Score-tracked obligations',
    tooltip:
      'Obligations counted in the compliance score projection. See Requirements for the full tracked registry.',
  },
  compliant_requirement_count: {
    label: 'Valid for scoring',
    tooltip: 'Projected COMPLIANT/VALID status in the score model — not the same as lifecycle verified.',
  },
  satisfied_requirement_count: {
    label: 'Lifecycle satisfied',
    tooltip: 'Recorded evidence (SATISFIED_UNVERIFIED) — assurance may still be pending.',
  },
  verified_requirement_count: {
    label: 'Lifecycle verified',
    tooltip: 'Platform-verified lifecycle state.',
  },
  platform_review_pending_count: {
    label: 'Awaiting review',
    tooltip: 'Evidence submitted; platform review pending.',
  },
};

export const LIVE_EXPORT_DISCLOSURE =
  'This download reflects current portfolio state and may differ from earlier exports.';

export const AUDIT_PACK_IMMUTABLE_DISCLOSURE =
  'Governed audit artifact: stored at generation with manifest checksums. Re-download returns the same file.';

export const OPERATIONAL_ZIP_DISCLOSURE =
  'Operational CSV/ZIP export — not regulator-grade. Use Audit Evidence Pack for evidentiary review.';

/**
 * @param {Record<string, unknown>|null|undefined} payload reporting_semantics from API
 */
export function countsFromReportingSemantics(payload) {
  const c = payload?.counts;
  return c && typeof c === 'object' ? c : null;
}
