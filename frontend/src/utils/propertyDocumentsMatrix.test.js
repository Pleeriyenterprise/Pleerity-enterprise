import { buildNeedsAttentionSubset, isRequirementActionRequired, requirementAttentionStatusRank } from './propertyDocumentsMatrix';

function req(id, status, extra = {}) {
  return {
    requirement_id: id,
    status,
    requirement_code: id,
    criticality: 'MED',
    due_date: `2026-01-${String(10 + Number(id.replace(/\D/g, '') || 0)).padStart(2, '0')}T00:00:00+00:00`,
    take_action: { primary: { route: `/properties/p/requirements/${id}`, label: 'Act' } },
    ...extra,
  };
}

describe('buildNeedsAttentionSubset', () => {
  it('caps results and returns overflow count', () => {
    const rows = Array.from({ length: 12 }).map((_, i) => req(`r${i + 1}`, 'MISSING'));
    const out = buildNeedsAttentionSubset(rows, (r) => r.due_date, 8);
    expect(out.items).toHaveLength(8);
    expect(out.total).toBe(12);
    expect(out.overflowCount).toBe(4);
  });

  it('applies priority ordering contract', () => {
    const rows = [
      req('followup', 'PENDING', { evidence_doc_id: 'doc-1' }),
      req('expiring', 'EXPIRING_SOON'),
      req('missing-high', 'MISSING', { criticality: 'HIGH' }),
      req('expired', 'EXPIRED'),
      req('incomplete', 'VALID', { workflow_class: 'MULTI_EVIDENCE' }),
      req('overdue', 'OVERDUE'),
    ];
    const out = buildNeedsAttentionSubset(rows, (r) => r.due_date, 8);
    expect(out.items.map((r) => r.requirement_id)).toEqual([
      'overdue',
      'expired',
      'missing-high',
      'expiring',
      'incomplete',
    ]);
  });

  it('treats legacy GUIDED_EVIDENCE_RESOLUTION like MULTI_EVIDENCE for attention-status rank (incomplete evidence)', () => {
    const legacy = req('legacy-guided', 'VALID', { workflow_class: 'GUIDED_EVIDENCE_RESOLUTION' });
    const multi = req('multi', 'VALID', { workflow_class: 'MULTI_EVIDENCE' });
    expect(requirementAttentionStatusRank(legacy)).toBe(requirementAttentionStatusRank(multi));
    expect(requirementAttentionStatusRank(legacy)).toBe(5);
  });

  it('orders urgency tier 1 before tier 2 before tier 3', () => {
    const rows = [
      req('pat', 'MISSING', { requirement_code: 'portable_appliance_test' }),
      req('leg', 'MISSING', { requirement_code: 'legionella' }),
      req('gas', 'MISSING', { requirement_code: 'gas_safety' }),
    ];
    const out = buildNeedsAttentionSubset(rows, (r) => r.due_date, 8);
    expect(out.items.map((r) => r.requirement_id)).toEqual(['gas', 'leg', 'pat']);
  });

  it('defers tier 3 rows when the cap is filled by tier 1 and tier 2', () => {
    const rows = [
      ...Array.from({ length: 5 }).map((_, i) => req(`gas${i}`, 'MISSING', { requirement_code: 'gas_safety' })),
      ...Array.from({ length: 5 }).map((_, i) => req(`leg${i}`, 'MISSING', { requirement_code: 'legionella' })),
      req('pat', 'MISSING', { requirement_code: 'portable_appliance_test' }),
    ];
    const out = buildNeedsAttentionSubset(rows, (r) => r.due_date, 8);
    expect(out.items).toHaveLength(8);
    expect(out.items.some((r) => r.requirement_id === 'pat')).toBe(false);
    expect(out.overflowCount).toBeGreaterThan(0);
  });

  it('excludes VALID/COMPLIANT rows with no follow-up and complete evidence', () => {
    const rows = [
      req('ok', 'VALID', { evidence_completeness: { summary_label: 'COMPLETE' } }),
      req('bad', 'MISSING', { requirement_code: 'eicr' }),
    ];
    const out = buildNeedsAttentionSubset(rows, (r) => r.due_date, 8);
    expect(out.items.map((r) => r.requirement_id)).toEqual(['bad']);
  });

  it('excludes satisfied non-document requirements still marked PENDING at engine level', () => {
    const rows = [
      req('legionella', 'PENDING', {
        requirement_code: 'legionella',
        requirement_satisfied: true,
        requirement_attention_eligible: false,
        missing_required_document: false,
        client_lifecycle_state: 'SATISFIED_UNVERIFIED',
        truth_presentation_stage: 'assessment_recorded',
      }),
      req('smoke', 'PENDING', {
        requirement_code: 'smoke_heat_alarms',
        requirement_satisfied: true,
        requirement_attention_eligible: false,
        missing_required_document: false,
        client_lifecycle_state: 'SATISFIED_UNVERIFIED',
        truth_presentation_stage: 'declaration_recorded',
      }),
      req('gas', 'PENDING', {
        requirement_code: 'gas_safety',
        requirement_satisfied: true,
        requirement_attention_eligible: false,
        missing_required_document: false,
        evidence_doc_id: 'doc-gas',
        client_lifecycle_state: 'VERIFIED',
      }),
      req('open', 'MISSING', { requirement_code: 'eicr' }),
    ];
    const out = buildNeedsAttentionSubset(rows, (r) => r.due_date, 8);
    expect(out.items.map((r) => r.requirement_id)).toEqual(['open']);
    expect(rows.filter((r) => isRequirementActionRequired(r)).map((r) => r.requirement_id)).toEqual(['open']);
  });
});

