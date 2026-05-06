import { buildNeedsAttentionSubset } from './propertyDocumentsMatrix';

function req(id, status, extra = {}) {
  return {
    requirement_id: id,
    status,
    requirement_code: id,
    criticality: 'MED',
    due_date: `2026-01-${String(10 + Number(id.replace(/\D/g, '') || 0)).padStart(2, '0')}T00:00:00+00:00`,
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
      'followup',
      'incomplete',
    ]);
  });
});

