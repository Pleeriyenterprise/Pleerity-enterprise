import { buildRentLedgerParams } from './rentKpiCoupling';
import { RENT_KPI_CARDS, rentKpiCompatibleWithTab, rentKpiTargetTab, rentListCountHint } from './rentKpiCopy';

describe('rentKpiCopy', () => {
  it('routes upcoming KPI to ledger tab', () => {
    const card = RENT_KPI_CARDS.find((c) => c.key === 'upcoming');
    expect(rentKpiTargetTab(card)).toBe('ledger');
    expect(rentKpiCompatibleWithTab(card, 'ledger')).toBe(true);
    expect(rentKpiCompatibleWithTab(card, 'attention')).toBe(false);
  });

  it('routes arrears KPI to attention tab', () => {
    const card = RENT_KPI_CARDS.find((c) => c.key === 'arrears');
    expect(rentKpiTargetTab(card)).toBe('attention');
    expect(rentKpiCompatibleWithTab(card, 'attention')).toBe(true);
  });

  it('rentListCountHint when total exceeds visible', () => {
    expect(rentListCountHint(200, 253)).toBe('Showing 200 of 253 periods');
    expect(rentListCountHint(5, 5)).toBeNull();
  });
});

describe('buildRentLedgerParams', () => {
  const upcoming = RENT_KPI_CARDS.find((c) => c.key === 'upcoming');

  it('uses UPCOMING status when upcoming KPI active on ledger tab', () => {
    const params = buildRentLedgerParams({
      tab: 'ledger',
      filterStatus: 'UPCOMING',
      activeKpi: upcoming,
    });
    expect(params.status).toBe('UPCOMING');
    expect(params.attention_only).toBeUndefined();
  });

  it('uses attention_only on attention tab even if upcoming KPI was active', () => {
    const params = buildRentLedgerParams({
      tab: 'attention',
      filterStatus: 'UPCOMING',
      activeKpi: upcoming,
    });
    expect(params.attention_only).toBe(true);
    expect(params.status).toBeUndefined();
  });

  it('uses overdue_only for overdue KPI on attention', () => {
    const overdue = RENT_KPI_CARDS.find((c) => c.key === 'overdue');
    const params = buildRentLedgerParams({
      tab: 'attention',
      activeKpi: overdue,
    });
    expect(params.overdue_only).toBe(true);
  });
});
