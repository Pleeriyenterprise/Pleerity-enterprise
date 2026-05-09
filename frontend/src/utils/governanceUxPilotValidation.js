/**
 * Governance-Aware UX Pilot — Phase 1 validation (read-only / audit-only).
 * Analyzes payload coverage, wording leakage risk, disclosure density, cognitive load,
 * fallback integrity, and aggregation behavior. Does not mutate UI or adapter outputs.
 */

import {
  GOVERNANCE_UX_PILOT_SCOPED_STATES,
  aggregateWorstPilotSemanticState,
  derivePilotSemanticState,
  getGovernanceUxPilotExportSurfaceNote,
  getGovernanceUxPilotPortfolioSupplementLine,
  getGovernanceUxPilotPresentation,
  mergeGovernanceUxPilotChip,
  resolvePilotDisclosurePresentation,
} from './governanceUxPilotAdapter.js';

/** @typedef {'LOW_DISCLOSURE_NOISE'|'MODERATE_DISCLOSURE_NOISE'|'HIGH_DISCLOSURE_NOISE'|'EXCESSIVE_DISCLOSURE_STACKING'} DisclosureNoiseClass */
/** @typedef {'LOW_COGNITIVE_IMPACT'|'MODERATE_COGNITIVE_IMPACT'|'HIGH_COGNITIVE_IMPACT'} CognitiveLoadClass */
/** @typedef {'SAFE_AGGREGATION'|'SLIGHTLY_OVER_CONSERVATIVE'|'POTENTIAL_SEMANTIC_COLLAPSE'|'INSUFFICIENT_DISCLOSURE'} AggregationClass */

const LEAKAGE_PATTERNS = [
  { id: 'compliant', re: /\b(compliant|fully\s+compliant)\b/i },
  { id: 'resolved', re: /\bresolved\b/i },
  { id: 'passed', re: /\bpassed\b/i },
  { id: 'current', re: /\bcurrent\b/i },
  { id: 'verified', re: /\bverified\b/i },
];

const STEMS_FOR_OVERLAP = ['follow', 'verif', 'operat', 'evid', 'remediat', 'assess', 'expir', 'independ'];

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {'semantic_state'|'evidence_authority.semantic_state'|'evidence_state'|'semantic_state_out_of_scope'|'evidence_authority_out_of_scope'|null}
 */
export function tracePilotSemanticPayloadSource(row) {
  if (!row || typeof row !== 'object') return null;
  const top = String(row.semantic_state || '').trim().toUpperCase();
  if (top && GOVERNANCE_UX_PILOT_SCOPED_STATES.has(top)) return 'semantic_state';
  const ea = row.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  const nested = String(ea?.semantic_state || '').trim().toUpperCase();
  if (nested && GOVERNANCE_UX_PILOT_SCOPED_STATES.has(nested)) return 'evidence_authority.semantic_state';
  const ev = String(row.evidence_state || '').trim().toUpperCase();
  if (ev === 'VERIFIED_CURRENT') return 'evidence_state';
  if (top) return 'semantic_state_out_of_scope';
  if (nested) return 'evidence_authority_out_of_scope';
  return null;
}

/**
 * @param {string} text
 * @param {string} semanticState
 * @param {string} surface
 * @param {string} field
 * @returns {Array<{ tokenId: string, surface: string, semanticState: string, field: string, sourceWording: string }>}
 */
export function findProhibitedWordingLeakageInText(text, semanticState, surface, field) {
  if (semanticState === 'VERIFIED_CURRENT') return [];
  const t = String(text || '');
  const out = [];
  for (const { id, re } of LEAKAGE_PATTERNS) {
    if (re.test(t)) {
      out.push({
        tokenId: id,
        surface,
        semanticState,
        field,
        sourceWording: t.slice(0, 240),
      });
    }
  }
  return out;
}

/**
 * Pilot-rendered strings for a semantic state (post-sanitizer paths used by adapter).
 * @param {string} semanticState
 */
function pilotRenderedStringsForState(semanticState) {
  const chip = getGovernanceUxPilotPresentation('CLIENT_STATUS_CHIP', semanticState);
  const port = getGovernanceUxPilotPresentation('PORTFOLIO_SCORE', semanticState);
  const out = [];
  if (chip) {
    out.push({ surface: 'CLIENT_STATUS_CHIP', field: 'compactLabel', text: chip.compactLabel });
    out.push({ surface: 'CLIENT_STATUS_CHIP', field: 'subline', text: chip.subline });
    out.push({ surface: 'CLIENT_STATUS_CHIP', field: 'disclosure', text: chip.disclosure });
  }
  if (port) {
    out.push({ surface: 'PORTFOLIO_SCORE', field: 'compactLabel', text: port.compactLabel });
    out.push({ surface: 'PORTFOLIO_SCORE', field: 'subline', text: port.subline });
    out.push({ surface: 'PORTFOLIO_SCORE', field: 'disclosure', text: port.disclosure });
  }
  const oneRow = [{ semantic_state: semanticState }];
  const pLine = getGovernanceUxPilotPortfolioSupplementLine(oneRow);
  if (pLine) out.push({ surface: 'PORTFOLIO_SCORE', field: 'portfolioSupplementLine', text: pLine });
  const ex = getGovernanceUxPilotExportSurfaceNote(oneRow);
  if (ex) out.push({ surface: 'REPORT_EXPORT', field: 'exportSurfaceNote', text: ex });
  return out;
}

/**
 * @param {unknown[]} requirements
 */
export function auditProhibitedWordingLeakageForPilotCatalog(requirements) {
  const findings = [];
  for (const st of GOVERNANCE_UX_PILOT_SCOPED_STATES) {
    const state = String(st);
    for (const { surface, field, text } of pilotRenderedStringsForState(state)) {
      findings.push(...findProhibitedWordingLeakageInText(text, state, surface, field));
    }
  }
  const baseChip = { icon: null, text: 'Valid', className: 'bg-green-100' };
  for (const st of GOVERNANCE_UX_PILOT_SCOPED_STATES) {
    const row = { semantic_state: st, evidence_doc_id: 'x', workflow_class: 'DOCUMENT_UPLOAD' };
    const merged = mergeGovernanceUxPilotChip({ ...baseChip }, row);
    findings.push(
      ...findProhibitedWordingLeakageInText(String(merged.text || ''), st, 'CLIENT_STATUS_CHIP', 'merged.text'),
    );
    findings.push(
      ...findProhibitedWordingLeakageInText(String(merged.subline || ''), st, 'CLIENT_STATUS_CHIP', 'merged.subline'),
    );
    const g = merged.governanceUxPilot;
    if (g && typeof g === 'object' && g.disclosure) {
      findings.push(
        ...findProhibitedWordingLeakageInText(String(g.disclosure), st, 'CLIENT_STATUS_CHIP', 'merged.governanceUxPilot.disclosure'),
      );
    }
  }
  if (Array.isArray(requirements) && requirements.length) {
    for (const row of requirements) {
      const st = derivePilotSemanticState(row);
      if (!st || st === 'VERIFIED_CURRENT') continue;
      const merged = mergeGovernanceUxPilotChip({ ...baseChip }, row);
      findings.push(
        ...findProhibitedWordingLeakageInText(String(merged.text || ''), st, 'CLIENT_STATUS_CHIP', 'row-merged.text'),
      );
      findings.push(
        ...findProhibitedWordingLeakageInText(String(merged.subline || ''), st, 'CLIENT_STATUS_CHIP', 'row-merged.subline'),
      );
    }
  }
  return { leakageCount: findings.length, findings };
}

function countStemOverlap(strings) {
  const joined = strings.join(' ').toLowerCase();
  return STEMS_FOR_OVERLAP.filter((s) => joined.includes(s)).length;
}

/**
 * @param {unknown[]} requirements
 * @returns {{ classification: DisclosureNoiseClass, detail: Record<string, unknown> }}
 */
export function classifyDisclosureNoise(requirements) {
  const worst = aggregateWorstPilotSemanticState(requirements);
  const portfolio = getGovernanceUxPilotPortfolioSupplementLine(requirements);
  const exportNote = getGovernanceUxPilotExportSurfaceNote(requirements);
  const chipDisclosureActive = !!worst && worst !== 'VERIFIED_CURRENT';
  const portfolioActive = !!portfolio;
  const exportActive = !!exportNote;

  const texts = [];
  if (portfolio) texts.push(portfolio);
  if (exportNote) texts.push(exportNote);
  if (worst && worst !== 'VERIFIED_CURRENT') {
    const p = getGovernanceUxPilotPresentation('CLIENT_STATUS_CHIP', worst);
    if (p?.disclosure) texts.push(p.disclosure);
    if (p?.subline) texts.push(p.subline);
  }
  const overlap = countStemOverlap(texts);
  const surfaceCount = [chipDisclosureActive, portfolioActive, exportActive].filter(Boolean).length;
  const joined = texts.join(' ');
  const sentenceFragments = joined ? joined.split(/[.!?]\s+/).filter(Boolean).length : 0;

  let classification = /** @type {DisclosureNoiseClass} */ ('LOW_DISCLOSURE_NOISE');
  if (sentenceFragments > 6) classification = 'EXCESSIVE_DISCLOSURE_STACKING';
  else if (surfaceCount >= 3 && overlap >= 4) classification = 'HIGH_DISCLOSURE_NOISE';
  else if (surfaceCount >= 3 && overlap >= 3) classification = 'MODERATE_DISCLOSURE_NOISE';
  else if (surfaceCount >= 2 && overlap >= 4) classification = 'MODERATE_DISCLOSURE_NOISE';
  else if (surfaceCount >= 3) classification = 'MODERATE_DISCLOSURE_NOISE';

  return {
    classification,
    detail: {
      worstAggregateState: worst,
      chipDisclosureMetadataActive: chipDisclosureActive,
      portfolioSupplementActive: portfolioActive,
      exportNoteActive: exportActive,
      activeSurfaceCount: surfaceCount,
      stemOverlapScore: overlap,
      combinedCharCount: texts.join(' ').length,
      redundantFollowUpPhrasing:
        portfolio && exportNote && /follow/i.test(portfolio) && /follow/i.test(exportNote),
    },
  };
}

/**
 * @param {unknown[]} requirements
 */
export function classifyCognitiveLoad(requirements) {
  const worst = aggregateWorstPilotSemanticState(requirements);
  const portfolio = getGovernanceUxPilotPortfolioSupplementLine(requirements);
  const exportNote = getGovernanceUxPilotExportSurfaceNote(requirements);
  let supportingLineCount = 0;
  if (portfolio) supportingLineCount += 1;
  if (exportNote) supportingLineCount += 1;
  if (worst && worst !== 'VERIFIED_CURRENT') {
    const chip = getGovernanceUxPilotPresentation('CLIENT_STATUS_CHIP', worst);
    if (chip?.subline) supportingLineCount += 1;
  }
  const disclosureBlocks = [!!portfolio, !!exportNote].filter(Boolean).length;
  const words = [portfolio, exportNote].filter(Boolean).join(' ').split(/\s+/).filter(Boolean).length;
  let classification = /** @type {CognitiveLoadClass} */ ('LOW_COGNITIVE_IMPACT');
  if (supportingLineCount > 2 || words > 55 || disclosureBlocks > 2) classification = 'HIGH_COGNITIVE_IMPACT';
  else if (supportingLineCount > 1 || words > 35) classification = 'MODERATE_COGNITIVE_IMPACT';

  return {
    classification,
    metrics: {
      supportingLineCount,
      disclosureBlockCount: disclosureBlocks,
      portfolioWordCount: portfolio ? portfolio.split(/\s+/).length : 0,
      exportWordCount: exportNote ? exportNote.split(/\s+/).length : 0,
    },
  };
}

/**
 * @param {unknown[]} requirements
 */
export function analyzePayloadCoverage(requirements) {
  const rows = Array.isArray(requirements) ? requirements : [];
  const total = rows.length;
  let semanticStateTop = 0;
  let nestedEaSemantic = 0;
  let evidenceStateVerifiedFallback = 0;
  let pilotResolved = 0;
  let verifiedCurrentDerived = 0;
  let semanticStateFieldPopulated = 0;
  let nestedSemanticFieldPopulated = 0;
  let evidenceStateFieldPopulated = 0;
  /** @type {Record<string, number>} */
  const unresolvedInventory = {};
  /** @type {Record<string, number>} */
  const sourceCounts = {};

  for (const row of rows) {
    if (String(row?.semantic_state || '').trim()) semanticStateFieldPopulated += 1;
    const ea0 = row?.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
    if (String(ea0?.semantic_state || '').trim()) nestedSemanticFieldPopulated += 1;
    if (String(row?.evidence_state || '').trim()) evidenceStateFieldPopulated += 1;

    const src = tracePilotSemanticPayloadSource(row);
    if (src) sourceCounts[src] = (sourceCounts[src] || 0) + 1;
    if (src === 'semantic_state') semanticStateTop += 1;
    if (src === 'evidence_authority.semantic_state') nestedEaSemantic += 1;
    if (src === 'evidence_state') evidenceStateVerifiedFallback += 1;

    const derived = derivePilotSemanticState(row);
    if (derived) {
      pilotResolved += 1;
      if (derived === 'VERIFIED_CURRENT') verifiedCurrentDerived += 1;
    } else {
      const top = String(row?.semantic_state || '').trim();
      const ea =
        row?.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
      const nested = String(ea?.semantic_state || '').trim();
      if (top || nested) {
        const key = top ? `semantic_state:${top}` : `evidence_authority.semantic_state:${nested}`;
        unresolvedInventory[key] = (unresolvedInventory[key] || 0) + 1;
      } else {
        unresolvedInventory['no_semantic_payload'] = (unresolvedInventory.no_semantic_payload || 0) + 1;
      }
    }
  }

  const pct = (n) => (total === 0 ? 0 : Math.round((n / total) * 10000) / 100);

  return {
    totalRows: total,
    rowsWithPilotDerivedState: pilotResolved,
    rowsSemanticStateTopScoped: semanticStateTop,
    rowsNestedEvidenceAuthorityScoped: nestedEaSemantic,
    rowsEvidenceStateVerifiedFallback: evidenceStateVerifiedFallback,
    rowsUnresolvedByPilotAdapter: total - pilotResolved,
    rowsVerifiedCurrentDerived: verifiedCurrentDerived,
    rowsSemanticStateFieldPopulated: semanticStateFieldPopulated,
    rowsNestedSemanticFieldPopulated: nestedSemanticFieldPopulated,
    rowsEvidenceStateFieldPopulated: evidenceStateFieldPopulated,
    percentages: {
      pilotResolvedPct: pct(pilotResolved),
      semanticStateTopScopedPct: pct(semanticStateTop),
      nestedEaScopedPct: pct(nestedEaSemantic),
      verifiedFallbackPct: pct(evidenceStateVerifiedFallback),
      unresolvedPct: pct(total - pilotResolved),
      semanticStateFieldPopulatedPct: pct(semanticStateFieldPopulated),
      nestedSemanticFieldPopulatedPct: pct(nestedSemanticFieldPopulated),
    },
    payloadSourceSummary: sourceCounts,
    unresolvedStateInventory: unresolvedInventory,
    fallbackRateSummary: {
      description:
        'Rows where derivePilotSemanticState returns null rely on legacy chip wording (no pilot overlay).',
      unresolvedCount: total - pilotResolved,
    },
  };
}

/**
 * @param {unknown[]} requirements
 */
export function auditFallbackIntegrity(requirements) {
  const baseChip = { icon: null, text: 'Legacy chip', className: 'x' };
  const issues = [];

  const noPilotRow = { status: 'COMPLIANT', evidence_doc_id: '1' };
  const mergedNone = mergeGovernanceUxPilotChip({ ...baseChip }, noPilotRow);
  if (mergedNone.text !== baseChip.text) {
    issues.push({ type: 'non_scoped_mutated', detail: 'merge changed chip without pilot signal' });
  }

  const scopedUnknown = { semantic_state: 'UNKNOWN_FUTURE_STATE', evidence_doc_id: '1' };
  const mergedUnknown = mergeGovernanceUxPilotChip({ ...baseChip }, scopedUnknown);
  if (mergedUnknown.text !== baseChip.text) {
    issues.push({ type: 'out_of_scope_mutated', detail: 'merge changed chip for non-scoped semantic_state string' });
  }

  const nullRow = null;
  try {
    mergeGovernanceUxPilotChip({ ...baseChip }, nullRow);
  } catch (e) {
    issues.push({ type: 'null_row_throw', detail: String(e) });
  }
  const mNull = mergeGovernanceUxPilotChip({ ...baseChip }, nullRow);
  if (mNull.text !== baseChip.text) issues.push({ type: 'null_row_text_changed' });

  const verified = mergeGovernanceUxPilotChip({ ...baseChip, subline: '' }, { semantic_state: 'VERIFIED_CURRENT', evidence_doc_id: '1' });
  if (!String(verified.text || '').toLowerCase().includes('verified')) {
    issues.push({ type: 'verified_compact_blocked', detail: verified.text });
  }

  const partial = mergeGovernanceUxPilotChip({ ...baseChip, text: 'Valid', subline: 'x' }, { semantic_state: 'PARTIALLY_COMPLETE', evidence_doc_id: '1' });
  if (partial.text === partial.subline) {
    issues.push({ type: 'duplicate_compact_subline', compact: partial.text, subline: partial.subline });
  }

  return {
    passed: issues.length === 0,
    issues,
    notes: [
      'VERIFIED_CURRENT may retain base subline when pilot subline empty.',
      'Non-scoped and missing semantic_state must preserve base chip text.',
    ],
  };
}

/**
 * @param {unknown[]} requirements
 */
export function auditAggregationBehavior(requirements) {
  const rows = Array.isArray(requirements) ? requirements : [];
  const worst = aggregateWorstPilotSemanticState(rows);
  const distinct = new Set();
  for (const r of rows) {
    const st = derivePilotSemanticState(r);
    if (st) distinct.add(st);
  }
  const portfolio = getGovernanceUxPilotPortfolioSupplementLine(rows);
  const exportNote = getGovernanceUxPilotExportSurfaceNote(rows);

  let classification = /** @type {AggregationClass} */ ('SAFE_AGGREGATION');
  const reasons = [];

  if (distinct.size > 1 && (portfolio || exportNote)) {
    classification = 'POTENTIAL_SEMANTIC_COLLAPSE';
    reasons.push(
      'Multiple distinct pilot states are summarized by a single worst-state aggregate disclosure (Phase 2: portfolio and/or export).',
    );
  }
  if (worst && distinct.size === 1 && worst !== 'VERIFIED_CURRENT' && !portfolio && !exportNote) {
    classification = 'INSUFFICIENT_DISCLOSURE';
    reasons.push('Worst state present but neither portfolio supplement nor export note is active (unexpected).');
  }
  if (distinct.size === 1 && worst === 'VERIFIED_CURRENT' && (portfolio || exportNote)) {
    classification = 'SLIGHTLY_OVER_CONSERVATIVE';
    reasons.push('Verified-only portfolio should not show risky supplement/export.');
  }
  if (rows.length && !worst && distinct.size === 0) {
    reasons.push('No pilot-derived states in set; aggregate surfaces inactive.');
  }

  return {
    classification,
    worstAggregateState: worst,
    distinctDerivedStates: [...distinct].sort(),
    reasons,
    export_note_active: !!exportNote,
    portfolio_supplement_active: !!portfolio,
    /** @deprecated name retained for audit diff — Phase 2 uses state-specific export when shown */
    exportUsesGenericRiskCopy: !!exportNote,
    portfolioTailoredToWorst: !!portfolio,
  };
}

function rankPilotSurfaces() {
  return {
    safestPilotSurfaces: ['CLIENT_STATUS_CHIP', 'PORTFOLIO_SCORE', 'REPORT_EXPORT'],
    highestRiskPilotSurfaces: ['REPORT_EXPORT', 'PORTFOLIO_SCORE', 'CLIENT_STATUS_CHIP'],
    rationale:
      'Phase 2: export is state-specific when shown and suppressed when portfolio already discloses (≥2 rows). Chips remain row-specific. Residual risk: aggregate lines use worst-of semantics across rows.',
  };
}

function rolloutReadinessFromSignals(payload, leakage, noise, cognitive, fallback, aggregation) {
  const blockers = [];
  if (leakage.leakageCount > 0) blockers.push('prohibited_wording_leakage');
  if (!fallback.passed) blockers.push('fallback_integrity_failure');
  if (noise.classification === 'EXCESSIVE_DISCLOSURE_STACKING' || noise.classification === 'HIGH_DISCLOSURE_NOISE') {
    blockers.push('disclosure_noise');
  }
  if (cognitive.classification === 'HIGH_COGNITIVE_IMPACT') blockers.push('cognitive_load');

  if (blockers.length) {
    return {
      recommendation: 'HOLD',
      blockers,
      narrative:
        'Resolve validation blockers before limited UI expansion. Pilot adapter copy remains frozen until leakage and integrity pass.',
    };
  }
  if (aggregation.classification === 'POTENTIAL_SEMANTIC_COLLAPSE') {
    return {
      recommendation: 'CONDITIONAL_GO',
      blockers: [],
      narrative:
        'Operationally safe for narrow pilot; aggregate surfaces still collapse distinct row semantics to one worst state — acceptable if stakeholders accept worst-of framing.',
    };
  }
  return {
    recommendation: 'GO_LIMITED_PILOT',
    blockers: [],
    narrative:
      'No automated blockers; payload coverage depends on API enrichment — monitor unresolved rate in production analytics.',
  };
}

function rollbackRecommendation() {
  return {
    recommendation: 'REVERT_ADAPTER_WIRING',
    narrative:
      'Remove mergeGovernanceUxPilotChip from getEvidenceStatus and pilot paragraphs from ComplianceScorePage; delete adapter and validation modules. No backend migration required.',
  };
}

/**
 * Stable JSON stringify (sorted object keys).
 * @param {unknown} obj
 */
export function stableStringifySnapshot(obj) {
  const sort = (v) => {
    if (v === null || typeof v !== 'object') return v;
    if (Array.isArray(v)) return v.map(sort);
    const o = {};
    for (const k of Object.keys(v).sort()) {
      o[k] = sort(v[k]);
    }
    return o;
  };
  return `${JSON.stringify(sort(obj), null, 2)}\n`;
}

/**
 * Build the Phase 1 governance UX pilot validation snapshot (audit payload).
 * @param {unknown[]} [requirements=[]] requirement rows as returned by /client/requirements (or similar).
 * @returns {Record<string, unknown>}
 */
export function buildGovernanceUxPilotValidationPhase1Snapshot(requirements = []) {
  const rows = Array.isArray(requirements) ? requirements : [];
  const payloadCoverage = analyzePayloadCoverage(rows);
  const wordingLeakage = auditProhibitedWordingLeakageForPilotCatalog(rows);
  const disclosureNoise = classifyDisclosureNoise(rows);
  const cognitiveLoad = classifyCognitiveLoad(rows);
  const fallbackIntegrity = auditFallbackIntegrity(rows);
  const aggregationBehavior = auditAggregationBehavior(rows);
  const surfaces = rankPilotSurfaces();
  const phase2Dedup = resolvePilotDisclosurePresentation(rows);

  const snapshot = {
    schema_version: 'governance_ux_pilot_validation_phase1_v1',
    generated_at: new Date().toISOString(),
    input_row_count: rows.length,
    payload_coverage_summary: payloadCoverage,
    unresolved_state_summary: {
      inventory: payloadCoverage.unresolvedStateInventory,
      fallback_rate: payloadCoverage.fallbackRateSummary,
    },
    wording_leakage_summary: {
      leakage_count: wordingLeakage.leakageCount,
      findings: wordingLeakage.findings,
    },
    disclosure_noise_summary: {
      classification: disclosureNoise.classification,
      detail: disclosureNoise.detail,
    },
    cognitive_load_summary: {
      classification: cognitiveLoad.classification,
      metrics: cognitiveLoad.metrics,
    },
    fallback_integrity_summary: fallbackIntegrity,
    aggregation_behavior_summary: aggregationBehavior,
    phase2_dedup_summary: {
      worst_state: phase2Dedup.worstState,
      portfolio: phase2Dedup.portfolio,
      export: phase2Dedup.export,
      export_suppressed: !!(phase2Dedup.worstState && phase2Dedup.worstState !== 'VERIFIED_CURRENT' && !phase2Dedup.export.text),
      portfolio_suppressed: !!(phase2Dedup.worstState && phase2Dedup.worstState !== 'VERIFIED_CURRENT' && !phase2Dedup.portfolio.text),
    },
    safest_pilot_surfaces: surfaces.safestPilotSurfaces,
    highest_risk_pilot_surfaces: surfaces.highestRiskPilotSurfaces,
    surface_risk_rationale: surfaces.rationale,
    rollout_readiness_recommendation: rolloutReadinessFromSignals(
      payloadCoverage,
      wordingLeakage,
      disclosureNoise,
      cognitiveLoad,
      fallbackIntegrity,
      aggregationBehavior,
    ),
    rollback_recommendation: rollbackRecommendation(),
    residual_risks: [
      'Pilot activation rate depends on API populating semantic_state or evidence_authority.semantic_state.',
      'Phase 2: aggregate worst-of framing can still differ from any single row’s semantic_state.',
      'Runtime UI was not modified by this validation module (audit-only).',
    ],
    runtime_behavior_changed: false,
    audit_only: true,
    non_blocking: true,
  };

  return snapshot;
}

/** Snake_case alias for audit pipelines */
export const build_governance_ux_pilot_validation_phase1_snapshot = buildGovernanceUxPilotValidationPhase1Snapshot;
