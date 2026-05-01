import { findRequirementRowForScoreDriver, scoreDriverRowReactKey } from './ComplianceScorePage.driverRemediation';

describe('ComplianceScorePage.driverRemediation', () => {
  it('matches requirement by property_id and requirement_id together (not requirement_id alone)', () => {
    const requirements = [
      { requirement_id: 'r1', property_id: 'p-a', take_action: { primary: { label: 'A', route: '/a', handler: 'navigate' } } },
      { requirement_id: 'r1', property_id: 'p-b', take_action: { primary: { label: 'B', route: '/b', handler: 'navigate' } } },
    ];
    const driver = { requirement_id: 'r1', property_id: 'p-b' };
    const row = findRequirementRowForScoreDriver(requirements, driver);
    expect(row?.take_action?.primary?.label).toBe('B');
  });

  it('scoreDriverRowReactKey stays distinct for same requirement_id under different gap_key', () => {
    const base = {
      property_id: 'p1',
      requirement_id: 'r1',
      status: 'MISSING_EVIDENCE',
      evidence_uploaded: false,
    };
    const k0 = scoreDriverRowReactKey({ ...base, gap_key: 'gap-a' }, 0);
    const k1 = scoreDriverRowReactKey({ ...base, gap_key: 'gap-b' }, 1);
    expect(k0).not.toBe(k1);
  });
});
