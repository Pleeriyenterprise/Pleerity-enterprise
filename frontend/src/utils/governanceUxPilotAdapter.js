/**
 * Governance-Aware UX Pilot — Phase 1 (narrow).
 * Pure planning/translation layer: maps backend-enriched semantic_state (and fallbacks) to
 * compact label + subline + disclosure guidance for CLIENT_STATUS_CHIP, PORTFOLIO_SCORE, REPORT_EXPORT surfaces.
 * Does not enforce runtime rules; does not change semantic derivation (read-only on row fields).
 */

/** @typedef {'CLIENT_STATUS_CHIP' | 'PORTFOLIO_SCORE' | 'REPORT_EXPORT'} GovernanceUxPilotSurface */

export const GOVERNANCE_UX_PILOT_SCOPED_STATES = new Set([
  'DECLARATION_RECORDED',
  'PARTIALLY_COMPLETE',
  'EXPIRY_REVIEW_REQUIRED',
  'ASSESSMENT_FOLLOWUP_REQUIRED',
  'OPERATIONALLY_OPEN',
  'VERIFIED_CURRENT',
]);

const PROHIBITED_TOKENS = /\b(compliant|fully compliant|resolved|passed)\b/gi;
const PROHIBITED_CURRENT_VERIFIED_UNSAFE =
  /\b(current|verified)\b/gi; // unsafe except VERIFIED_CURRENT — stripped in sanitizer

/**
 * Read semantic state from enriched requirement rows (evidence_authority.semantic_state or semantic_state).
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {string|null}
 */
export function derivePilotSemanticState(row) {
  if (!row || typeof row !== 'object') return null;
  const top = String(row.semantic_state || '').trim().toUpperCase();
  if (GOVERNANCE_UX_PILOT_SCOPED_STATES.has(top)) return top;
  const ea = row.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  const nested = String(ea?.semantic_state || '').trim().toUpperCase();
  if (GOVERNANCE_UX_PILOT_SCOPED_STATES.has(nested)) return nested;
  const ev = String(row.evidence_state || '').trim().toUpperCase();
  if (ev === 'VERIFIED_CURRENT') return 'VERIFIED_CURRENT';
  return null;
}

/**
 * @param {string} text
 * @param {string} semanticState
 */
function sanitizePilotCopy(text, semanticState) {
  let t = String(text || '');
  t = t.replace(PROHIBITED_TOKENS, '').replace(/\s{2,}/g, ' ').trim();
  if (semanticState !== 'VERIFIED_CURRENT') {
    t = t.replace(PROHIBITED_CURRENT_VERIFIED_UNSAFE, '').replace(/\s{2,}/g, ' ').trim();
  }
  return t || '—';
}

const CHIP_PRESENTATION = {
  DECLARATION_RECORDED: {
    compactLabel: 'Declaration recorded',
    subline: 'Independent verification pending',
    disclosure: 'Self-declared information may not yet be independently verified.',
    severity: 'attention',
    requiresDisclosure: true,
    requiresExpandedContext: false,
    prohibitedSimplifications: ['Compliant', 'Verified', 'Current', 'Resolved'],
  },
  PARTIALLY_COMPLETE: {
    compactLabel: 'Partially complete',
    subline: 'Additional evidence required',
    disclosure: 'Additional evidence is still required for some items.',
    severity: 'attention',
    requiresDisclosure: true,
    requiresExpandedContext: false,
    prohibitedSimplifications: ['Complete', 'Compliant', 'Resolved'],
  },
  EXPIRY_REVIEW_REQUIRED: {
    compactLabel: 'Expiry review due',
    subline: 'Validity requires confirmation',
    disclosure: 'Validity may require review of expiry information before relying on it.',
    severity: 'attention',
    requiresDisclosure: true,
    requiresExpandedContext: false,
    prohibitedSimplifications: ['Current', 'Valid', 'Compliant', 'Up to date'],
  },
  ASSESSMENT_FOLLOWUP_REQUIRED: {
    compactLabel: 'Follow-up required',
    subline: 'Operational action still open',
    disclosure: 'Further assessment or remediation may still be required.',
    severity: 'attention',
    requiresDisclosure: true,
    requiresExpandedContext: false,
    prohibitedSimplifications: ['Passed', 'Resolved', 'Complete', 'Closed'],
  },
  OPERATIONALLY_OPEN: {
    compactLabel: 'Operationally open',
    subline: 'Pending operational follow-through',
    disclosure: 'Operational work may not be closed even when documents are on file.',
    severity: 'attention',
    requiresDisclosure: true,
    requiresExpandedContext: false,
    prohibitedSimplifications: ['Complete', 'Resolved', 'Compliant'],
  },
  VERIFIED_CURRENT: {
    compactLabel: 'Verified current',
    subline: '',
    disclosure: '',
    severity: 'ok',
    requiresDisclosure: false,
    requiresExpandedContext: false,
    prohibitedSimplifications: [],
  },
};

/**
 * Phase 2: portfolio-level lines only — must not echo chip sublines (e.g. avoid repeating
 * “Additional evidence required” / “Follow-up required” verbatim).
 */
const PORTFOLIO_SUPPLEMENT = {
  DECLARATION_RECORDED: 'Some properties include declarations that may need portfolio-level confirmation.',
  PARTIALLY_COMPLETE: 'Certain compliance items remain under assessment across the portfolio.',
  EXPIRY_REVIEW_REQUIRED: 'Some properties may need expiry timing checked at portfolio level.',
  ASSESSMENT_FOLLOWUP_REQUIRED: 'Some properties still have open assessment or review actions.',
  OPERATIONALLY_OPEN: 'Some properties still have open operational items at portfolio level.',
  VERIFIED_CURRENT: null,
};

/** Phase 2: state-specific export copy (single short line each). */
const EXPORT_NOTE_BY_STATE = {
  PARTIALLY_COMPLETE: 'Some records may still require additional evidence.',
  EXPIRY_REVIEW_REQUIRED: 'Some records may require expiry-date review.',
  ASSESSMENT_FOLLOWUP_REQUIRED: 'Operational follow-up may still be required for certain items.',
  DECLARATION_RECORDED: 'Some records are awaiting independent verification.',
  OPERATIONALLY_OPEN: 'Operational work may remain open on certain items.',
};

/** @typedef {'DISCLOSURE_PRIMARY' | 'DISCLOSURE_SECONDARY' | 'DISCLOSURE_SUPPRESSED'} GovernanceUxPilotDisclosureClassification */

/** @type {Record<string, number>} lower = higher priority risk */
const WORST_STATE_RANK = {
  OPERATIONALLY_OPEN: 10,
  ASSESSMENT_FOLLOWUP_REQUIRED: 20,
  EXPIRY_REVIEW_REQUIRED: 30,
  PARTIALLY_COMPLETE: 40,
  DECLARATION_RECORDED: 50,
  VERIFIED_CURRENT: 100,
};

/**
 * @param {GovernanceUxPilotSurface} surface
 * @param {string} semanticState
 * @returns {null | {
 *   compactLabel: string,
 *   subline: string,
 *   disclosure: string,
 *   severity: string,
 *   requiresDisclosure: boolean,
 *   requiresExpandedContext: boolean,
 *   prohibitedSimplifications: string[],
 * }}
 */
export function getGovernanceUxPilotPresentation(surface, semanticState) {
  const st = String(semanticState || '').trim().toUpperCase();
  if (!GOVERNANCE_UX_PILOT_SCOPED_STATES.has(st)) return null;
  const chip = CHIP_PRESENTATION[st];
  if (!chip) return null;
  const base = { ...chip, prohibitedSimplifications: [...chip.prohibitedSimplifications] };
  if (surface === 'CLIENT_STATUS_CHIP') {
    return {
      ...base,
      compactLabel: sanitizePilotCopy(base.compactLabel, st),
      subline: base.subline ? sanitizePilotCopy(base.subline, st) : '',
      disclosure: base.disclosure ? sanitizePilotCopy(base.disclosure, st) : '',
    };
  }
  if (surface === 'PORTFOLIO_SCORE' || surface === 'REPORT_EXPORT') {
    return {
      ...base,
      compactLabel: sanitizePilotCopy(base.compactLabel, st),
      subline: base.subline ? sanitizePilotCopy(base.subline, st) : '',
      disclosure: base.disclosure ? sanitizePilotCopy(base.disclosure, st) : '',
    };
  }
  return null;
}

/**
 * Merge pilot chip copy onto existing evidence chip config (additive text only).
 * @param {Record<string, unknown>} baseChip from getEvidenceStatus
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {Record<string, unknown>}
 */
export function mergeGovernanceUxPilotChip(baseChip, row) {
  const st = derivePilotSemanticState(row);
  if (!st) return baseChip;
  const pilot = getGovernanceUxPilotPresentation('CLIENT_STATUS_CHIP', st);
  if (!pilot) return baseChip;
  const out = { ...baseChip };
  out.text = pilot.compactLabel;
  if (pilot.subline) {
    out.subline = pilot.subline;
  } else if (st === 'VERIFIED_CURRENT' && baseChip.subline) {
    out.subline = baseChip.subline;
  }
  out.governanceUxPilot = {
    disclosure: pilot.disclosure,
    severity: pilot.severity,
    requiresDisclosure: pilot.requiresDisclosure,
    requiresExpandedContext: pilot.requiresExpandedContext,
    prohibitedSimplifications: pilot.prohibitedSimplifications,
    semanticState: st,
  };
  return out;
}

/**
 * Worst (highest-risk) pilot semantic state across requirement rows.
 * @param {unknown[]} requirements
 * @returns {string|null}
 */
export function aggregateWorstPilotSemanticState(requirements) {
  if (!Array.isArray(requirements) || requirements.length === 0) return null;
  let worst = null;
  let worstRank = Infinity;
  for (const r of requirements) {
    const st = derivePilotSemanticState(r);
    if (!st || !GOVERNANCE_UX_PILOT_SCOPED_STATES.has(st)) continue;
    const rank = WORST_STATE_RANK[st] ?? 999;
    if (rank < worstRank) {
      worstRank = rank;
      worst = st;
    }
  }
  return worst;
}

/**
 * Phase 2 — deterministic disclosure priority for aggregate score-screen surfaces.
 * Chip/subline stays primary on requirement rows; this only splits portfolio supplement vs export note.
 *
 * - **≥2 rows:** portfolio line when worst is risky (aggregate framing); export suppressed (avoids duplicate warnings).
 * - **1 row:** export note state-specific when worst is risky; portfolio suppressed (chip already carries row truth).
 *
 * @param {unknown[]} requirements
 * @returns {{
 *   worstState: string|null,
 *   portfolio: { text: string|null, classification: GovernanceUxPilotDisclosureClassification, suppressionReason: string|null },
 *   export: { text: string|null, classification: GovernanceUxPilotDisclosureClassification, suppressionReason: string|null },
 * }}
 */
export function resolvePilotDisclosurePresentation(requirements) {
  const rows = Array.isArray(requirements) ? requirements : [];
  const worst = aggregateWorstPilotSemanticState(rows);

  const empty = {
    worstState: null,
    portfolio: {
      text: null,
      classification: /** @type {GovernanceUxPilotDisclosureClassification} */ ('DISCLOSURE_SUPPRESSED'),
      suppressionReason: 'no_risky_aggregate',
    },
    export: {
      text: null,
      classification: /** @type {GovernanceUxPilotDisclosureClassification} */ ('DISCLOSURE_SUPPRESSED'),
      suppressionReason: 'no_risky_aggregate',
    },
  };

  if (!worst || worst === 'VERIFIED_CURRENT') {
    return empty;
  }

  const n = rows.length;
  const pf = PORTFOLIO_SUPPLEMENT[worst];
  const rawExportTemplate = EXPORT_NOTE_BY_STATE[worst];

  if (n >= 2) {
    const portfolioText = pf ? sanitizePilotCopy(pf, worst) : null;
    return {
      worstState: worst,
      portfolio: {
        text: portfolioText,
        classification: portfolioText ? 'DISCLOSURE_PRIMARY' : 'DISCLOSURE_SUPPRESSED',
        suppressionReason: portfolioText ? null : 'no_portfolio_copy_for_state',
      },
      export: {
        text: null,
        classification: 'DISCLOSURE_SUPPRESSED',
        suppressionReason: 'suppressed_portfolio_primary_aggregate',
      },
    };
  }

  const exportText = rawExportTemplate ? sanitizePilotCopy(rawExportTemplate, worst) : null;
  return {
    worstState: worst,
    portfolio: {
      text: null,
      classification: 'DISCLOSURE_SUPPRESSED',
      suppressionReason: 'suppressed_chip_primary_single_row',
    },
    export: {
      text: exportText,
      classification: exportText ? 'DISCLOSURE_SECONDARY' : 'DISCLOSURE_SUPPRESSED',
      suppressionReason: exportText ? 'single_row_state_specific_export' : 'no_export_copy_for_state',
    },
  };
}

/**
 * One supporting line for portfolio score summary when portfolio carries pilot risky semantics.
 * @param {unknown[]} requirements
 * @returns {string|null}
 */
export function getGovernanceUxPilotPortfolioSupplementLine(requirements) {
  return resolvePilotDisclosurePresentation(requirements).portfolio.text;
}

/**
 * Short disclosure note for score PDF/CSV export area (Phase 2: deduped vs portfolio; state-specific when shown).
 * @param {unknown[]} requirements
 * @returns {string|null}
 */
export function getGovernanceUxPilotExportSurfaceNote(requirements) {
  return resolvePilotDisclosurePresentation(requirements).export.text;
}
