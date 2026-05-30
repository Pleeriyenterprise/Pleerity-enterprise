/**
 * Trust-language governance — canonical rules for customer-facing operational explanations.
 * Mirror: backend/services/trust_language_governance.py
 *
 * Principle: transparent operational outcomes, opaque implementation mechanics.
 */

/** @readonly */
export const SAFE_OPERATIONAL_LANGUAGE = [
  'accepted evidence',
  'overdue actions',
  'expiring records',
  'maintenance issues',
  'unresolved items',
  'review pending',
  'score may improve',
];

/** Engineering / model internals — must not appear in customer-visible copy. */
export const FORBIDDEN_ENGINEERING_TERMS = [
  'weighted contributions',
  're-aggregation',
  'scoring engine',
  'bucket emphasis',
  'credit within each bucket',
  'maintenance confidence',
  'operational responsiveness',
  '100 / 70 / 30 / 0',
  'document-backed operational summary',
  'risk-style weighting',
  'hand-tuned percentage',
  'design guide',
  'rigid formula',
  'approximate emphasis',
  '~60%',
  'points earned',
  'model weighting',
  'scoring formula',
  'heuristic allocation',
  'point distribution',
  'internal confidence model',
  'cvp score v',
  'status score',
  'expiry score',
  'document score',
  'overdue_penalty_score',
  'server-confirmed',
  'remediation step',
  'remediation metadata',
];

/** @type {RegExp[]} */
export const FORBIDDEN_FALSE_PRECISION_PATTERNS = [
  /\+\s*\d+\s*points?/i,
  /moved by\s*[+-]?\d+\s*points?/i,
  /changed by\s*\d+\s*points?/i,
  /improved by\s*\d+\s*points?/i,
  /score\s*[+-]\d+/i,
  /this guarantees/i,
];

/** Vague-only causality — flag when used as the sole explanation. */
export const VAGUE_CAUSAL_PATTERNS = [
  /based on recent activity/i,
  /recent changes affected your score/i,
  /system updates/i,
];

/** Copy authority registry — extend when adding explanation surfaces. */
export const COPY_AUTHORITY_REGISTRY = {
  portal_scoring_ui: 'frontend/src/utils/scoringExplanationCopy.js',
  portal_confidence: 'frontend/src/utils/confidenceUxCopy.js',
  portal_freshness: 'frontend/src/utils/scoreFreshnessUi.js',
  portal_workspace: 'frontend/src/utils/workspaceOrientationCopy.js',
  portal_jurisdiction: 'frontend/src/utils/jurisdictionComplianceCopy.js',
  portal_presentation: 'frontend/src/utils/presentationLanguage.js',
  backend_scoring_copy: 'backend/services/scoring_explanation_copy.py',
  backend_governance: 'backend/services/trust_language_governance.py',
};

/**
 * @param {string|null|undefined} text
 * @param {{ allowVague?: boolean }} [opts]
 * @returns {{ category: string, match: string }[]}
 */
export function validateCustomerCopy(text, opts = {}) {
  const { allowVague = false } = opts;
  if (!text || !String(text).trim()) return [];
  const violations = [];
  const low = String(text).toLowerCase();

  for (const term of FORBIDDEN_ENGINEERING_TERMS) {
    if (low.includes(term.toLowerCase())) {
      violations.push({ category: 'FORBIDDEN_ENGINEERING_LANGUAGE', match: term });
    }
  }
  for (const pat of FORBIDDEN_FALSE_PRECISION_PATTERNS) {
    if (pat.test(text)) {
      violations.push({ category: 'FORBIDDEN_FALSE_PRECISION', match: String(pat) });
    }
  }
  if (!allowVague) {
    for (const pat of VAGUE_CAUSAL_PATTERNS) {
      if (pat.test(text)) {
        violations.push({ category: 'VAGUE_CAUSAL_LANGUAGE', match: String(pat) });
      }
    }
  }
  return violations;
}

/** Back-compat alias for scoring explanation tests. */
export const SCORING_EXPLANATION_FORBIDDEN_TERMS = FORBIDDEN_ENGINEERING_TERMS.filter(
  (t) =>
    !['status score', 'expiry score', 'document score', 'overdue_penalty_score'].includes(t)
);
