import {
  analyzePayloadCoverage,
  auditAggregationBehavior,
  auditFallbackIntegrity,
  auditProhibitedWordingLeakageForPilotCatalog,
  buildGovernanceUxPilotValidationPhase1Snapshot,
  classifyCognitiveLoad,
  classifyDisclosureNoise,
  findProhibitedWordingLeakageInText,
  stableStringifySnapshot,
} from './governanceUxPilotValidation';

const DEMO_REQUIREMENTS = [
  { requirement_id: 'r1', semantic_state: 'PARTIALLY_COMPLETE', status: 'COMPLIANT' },
  { requirement_id: 'r2', semantic_state: 'OPERATIONALLY_OPEN', status: 'COMPLIANT' },
  { requirement_id: 'r3', semantic_state: 'VERIFIED_CURRENT', status: 'COMPLIANT' },
  { requirement_id: 'r4', semantic_state: 'UNKNOWN_CUSTOM', status: 'COMPLIANT' },
  { requirement_id: 'r5', evidence_authority: { semantic_state: 'DECLARATION_RECORDED' }, status: 'COMPLIANT' },
  { requirement_id: 'r6', evidence_state: 'VERIFIED_CURRENT', status: 'COMPLIANT' },
  { requirement_id: 'r7', status: 'COMPLIANT' },
];

describe('governanceUxPilotValidation', () => {
  it('coverage determinism for fixed fixture', () => {
    const a = analyzePayloadCoverage(DEMO_REQUIREMENTS);
    const b = analyzePayloadCoverage(DEMO_REQUIREMENTS);
    expect(a).toEqual(b);
    expect(a.totalRows).toBe(7);
    expect(a.rowsWithPilotDerivedState).toBe(5);
    expect(a.rowsUnresolvedByPilotAdapter).toBe(2);
    expect(a.rowsSemanticStateTopScoped).toBe(3);
    expect(a.rowsNestedEvidenceAuthorityScoped).toBe(1);
    expect(a.rowsEvidenceStateVerifiedFallback).toBe(1);
    expect(a.rowsSemanticStateFieldPopulated).toBe(4);
    expect(a.rowsNestedSemanticFieldPopulated).toBe(1);
    expect(a.unresolvedStateInventory['semantic_state:UNKNOWN_CUSTOM']).toBe(1);
    expect(a.unresolvedStateInventory.no_semantic_payload).toBe(1);
    expect(Object.keys(a.unresolvedStateInventory).length).toBe(2);
  });

  it('wording leakage detection allows verified for VERIFIED_CURRENT only', () => {
    expect(findProhibitedWordingLeakageInText('Verified current', 'VERIFIED_CURRENT', 'X', 'f')).toEqual([]);
    const leaks = findProhibitedWordingLeakageInText('Fully compliant now', 'PARTIALLY_COMPLETE', 'CHIP', 't');
    expect(leaks.some((x) => x.tokenId === 'compliant')).toBe(true);
  });

  it('catalog leakage scan passes for current pilot adapter strings', () => {
    const { leakageCount, findings } = auditProhibitedWordingLeakageForPilotCatalog(DEMO_REQUIREMENTS);
    expect(leakageCount).toBe(0);
    expect(findings).toEqual([]);
  });

  it('disclosure-noise classification for mixed risky states', () => {
    const noise = classifyDisclosureNoise(DEMO_REQUIREMENTS);
    expect(['MODERATE_DISCLOSURE_NOISE', 'HIGH_DISCLOSURE_NOISE', 'LOW_DISCLOSURE_NOISE']).toContain(noise.classification);
    expect(noise.detail.activeSurfaceCount).toBeGreaterThanOrEqual(2);
    expect(noise.detail.worstAggregateState).toBe('OPERATIONALLY_OPEN');
  });

  it('cognitive load stays moderate or low for pilot (max one supplement + one export)', () => {
    const c = classifyCognitiveLoad(DEMO_REQUIREMENTS);
    expect(['LOW_COGNITIVE_IMPACT', 'MODERATE_COGNITIVE_IMPACT', 'HIGH_COGNITIVE_IMPACT']).toContain(c.classification);
    expect(c.metrics.supportingLineCount).toBeLessThanOrEqual(3);
  });

  it('fallback integrity detection passes', () => {
    const f = auditFallbackIntegrity(DEMO_REQUIREMENTS);
    expect(f.passed).toBe(true);
    expect(f.issues).toEqual([]);
  });

  it('aggregation classification flags generic export under mixed states', () => {
    const agg = auditAggregationBehavior(DEMO_REQUIREMENTS);
    expect(agg.distinctDerivedStates.sort()).toEqual([
      'DECLARATION_RECORDED',
      'OPERATIONALLY_OPEN',
      'PARTIALLY_COMPLETE',
      'VERIFIED_CURRENT',
    ]);
    expect(agg.classification).toBe('POTENTIAL_SEMANTIC_COLLAPSE');
    expect(agg.portfolio_supplement_active).toBe(true);
    expect(agg.export_note_active).toBe(false);
  });

  it('snapshot includes Phase 2 dedup summary', () => {
    const snap = buildGovernanceUxPilotValidationPhase1Snapshot(DEMO_REQUIREMENTS);
    expect(snap.phase2_dedup_summary).toMatchObject({
      worst_state: 'OPERATIONALLY_OPEN',
      export_suppressed: true,
      portfolio_suppressed: false,
    });
    expect(snap.phase2_dedup_summary.export.suppressionReason).toMatch(/suppressed_portfolio/);
  });

  it('snapshot stability excluding generated_at', () => {
    const s1 = buildGovernanceUxPilotValidationPhase1Snapshot(DEMO_REQUIREMENTS);
    const s2 = buildGovernanceUxPilotValidationPhase1Snapshot(DEMO_REQUIREMENTS);
    delete s1.generated_at;
    delete s2.generated_at;
    expect(s1).toEqual(s2);
  });

  it('stableStringifySnapshot is deterministic for same input object shape', () => {
    const snap = buildGovernanceUxPilotValidationPhase1Snapshot([]);
    snap.generated_at = 'FIXED';
    const a = stableStringifySnapshot(snap);
    const b = stableStringifySnapshot(JSON.parse(a));
    expect(a).toBe(b);
  });

  it('non-scoped preservation: empty requirements yield safe rollout narrative', () => {
    const snap = buildGovernanceUxPilotValidationPhase1Snapshot([]);
    expect(snap.runtime_behavior_changed).toBe(false);
    expect(snap.audit_only).toBe(true);
    expect(snap.non_blocking).toBe(true);
    expect(snap.wording_leakage_summary.leakage_count).toBe(0);
    expect(snap.aggregation_behavior_summary.classification).toBe('SAFE_AGGREGATION');
  });

  it('root snapshot includes rollout and rollback blocks', () => {
    const snap = buildGovernanceUxPilotValidationPhase1Snapshot(DEMO_REQUIREMENTS);
    expect(snap.rollout_readiness_recommendation).toMatchObject({ recommendation: expect.any(String) });
    expect(snap.rollback_recommendation).toMatchObject({ recommendation: 'REVERT_ADAPTER_WIRING' });
    expect(Array.isArray(snap.safest_pilot_surfaces)).toBe(true);
    expect(Array.isArray(snap.highest_risk_pilot_surfaces)).toBe(true);
  });
});
