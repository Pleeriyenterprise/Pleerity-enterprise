import { getEvidenceStatus } from './evidenceStatus';
import {
  aggregateWorstPilotSemanticState,
  derivePilotSemanticState,
  getGovernanceUxPilotExportSurfaceNote,
  getGovernanceUxPilotPortfolioSupplementLine,
  getGovernanceUxPilotPresentation,
  mergeGovernanceUxPilotChip,
  resolvePilotDisclosurePresentation,
} from './governanceUxPilotAdapter';

describe('governanceUxPilotAdapter', () => {
  it('derives semantic_state from evidence_authority', () => {
    const row = { evidence_authority: { semantic_state: 'PARTIALLY_COMPLETE' } };
    expect(derivePilotSemanticState(row)).toBe('PARTIALLY_COMPLETE');
  });

  it('derives VERIFIED_CURRENT from evidence_state fallback', () => {
    const row = { evidence_state: 'VERIFIED_CURRENT' };
    expect(derivePilotSemanticState(row)).toBe('VERIFIED_CURRENT');
  });

  it('returns null when no pilot signal', () => {
    expect(derivePilotSemanticState({ compliance_state: 'MISSING' })).toBe(null);
  });

  it('exposes presentation for scoped states', () => {
    const p = getGovernanceUxPilotPresentation('CLIENT_STATUS_CHIP', 'DECLARATION_RECORDED');
    expect(p.compactLabel).toBe('Declaration recorded');
    expect(p.subline).toContain('Independent verification');
    expect(p.requiresDisclosure).toBe(true);
    expect(p.prohibitedSimplifications).toContain('Compliant');
  });

  it('VERIFIED_CURRENT allows compact label without disclosure requirement', () => {
    const p = getGovernanceUxPilotPresentation('CLIENT_STATUS_CHIP', 'VERIFIED_CURRENT');
    expect(p.requiresDisclosure).toBe(false);
    expect(p.compactLabel.toLowerCase()).toContain('verified');
  });

  it('aggregateWorstPilotSemanticState picks highest-risk state', () => {
    const reqs = [
      { semantic_state: 'VERIFIED_CURRENT' },
      { semantic_state: 'PARTIALLY_COMPLETE' },
      { evidence_authority: { semantic_state: 'OPERATIONALLY_OPEN' } },
    ];
    expect(aggregateWorstPilotSemanticState(reqs)).toBe('OPERATIONALLY_OPEN');
  });

  it('portfolio supplement null when only verified', () => {
    expect(getGovernanceUxPilotPortfolioSupplementLine([{ semantic_state: 'VERIFIED_CURRENT' }])).toBe(null);
  });

  it('portfolio supplement present for partial', () => {
    const line = getGovernanceUxPilotPortfolioSupplementLine([
      { semantic_state: 'PARTIALLY_COMPLETE' },
      { semantic_state: 'VERIFIED_CURRENT' },
    ]);
    expect(line).toMatch(/assessment|portfolio|properties/i);
    expect(line.toLowerCase()).not.toMatch(/additional evidence required/);
  });

  it('Phase 2: single-row risky shows export, suppresses portfolio (chip primary)', () => {
    const one = [{ semantic_state: 'PARTIALLY_COMPLETE' }];
    expect(getGovernanceUxPilotPortfolioSupplementLine(one)).toBe(null);
    expect(getGovernanceUxPilotExportSurfaceNote(one)).toMatch(/additional evidence/i);
    const r = resolvePilotDisclosurePresentation(one);
    expect(r.portfolio.classification).toBe('DISCLOSURE_SUPPRESSED');
    expect(r.export.classification).toBe('DISCLOSURE_SECONDARY');
  });

  it('Phase 2: multi-row risky shows portfolio, suppresses export', () => {
    const two = [{ semantic_state: 'PARTIALLY_COMPLETE' }, { semantic_state: 'VERIFIED_CURRENT' }];
    expect(getGovernanceUxPilotPortfolioSupplementLine(two)).toBeTruthy();
    expect(getGovernanceUxPilotExportSurfaceNote(two)).toBe(null);
    const r = resolvePilotDisclosurePresentation(two);
    expect(r.portfolio.classification).toBe('DISCLOSURE_PRIMARY');
    expect(r.export.classification).toBe('DISCLOSURE_SUPPRESSED');
  });

  it('export note state-specific for single-row declaration', () => {
    expect(getGovernanceUxPilotExportSurfaceNote([{ semantic_state: 'DECLARATION_RECORDED' }])).toMatch(/awaiting independent verification/i);
  });

  it('export note absent when only verified', () => {
    expect(getGovernanceUxPilotExportSurfaceNote([{ semantic_state: 'VERIFIED_CURRENT' }])).toBe(null);
  });

  it('sanitizes prohibited tokens from pilot copy paths', () => {
    const base = { icon: null, text: 'Valid', className: 'x' };
    const row = { semantic_state: 'PARTIALLY_COMPLETE' };
    const merged = mergeGovernanceUxPilotChip(base, row);
    expect(merged.text).toBe('Partially complete');
    expect(merged.subline).toMatch(/Additional evidence/);
  });
});

describe('governanceUxPilot chip integration', () => {
  it('overlays chip for PARTIALLY_COMPLETE semantic_state on compliant status', () => {
    const row = { semantic_state: 'PARTIALLY_COMPLETE', evidence_doc_id: '1', workflow_class: 'DOCUMENT_UPLOAD' };
    const chip = getEvidenceStatus('COMPLIANT', row);
    expect(chip.text).toBe('Partially complete');
    expect(chip.subline).toMatch(/Additional evidence/);
    expect(chip.governanceUxPilot?.semanticState).toBe('PARTIALLY_COMPLETE');
  });

  it('does not alter chip when semantic_state absent', () => {
    const row = { workflow_class: 'DOCUMENT_UPLOAD', evidence_doc_id: '1' };
    const chip = getEvidenceStatus('COMPLIANT', row);
    expect(chip.text).toBe('Valid');
  });
});
