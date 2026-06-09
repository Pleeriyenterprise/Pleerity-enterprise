import {
  canConfirmRentSchedule,
  filterTenanciesForProperty,
  pickDefaultTenancyId,
  tenancyBelongsToProperty,
} from './rentScheduleTenancy';

describe('rentScheduleTenancy', () => {
  const tenancies = [
    { tenancy_id: 'pty_a', property_id: 'prop-a', status: 'active' },
    { tenancy_id: 'pty_b', property_id: 'prop-b', status: 'active' },
  ];

  it('filters tenancies strictly by property', () => {
    expect(filterTenanciesForProperty(tenancies, 'prop-a')).toEqual([tenancies[0]]);
    expect(filterTenanciesForProperty(tenancies, 'prop-b')).toEqual([tenancies[1]]);
    expect(filterTenanciesForProperty(tenancies, 'prop-c')).toEqual([]);
  });

  it('rejects cross-property tenancy selection', () => {
    expect(tenancyBelongsToProperty('pty_b', tenancies, 'prop-a')).toBe(false);
    expect(tenancyBelongsToProperty('pty_a', tenancies, 'prop-a')).toBe(true);
  });

  it('preselects when exactly one active tenancy exists', () => {
    expect(pickDefaultTenancyId([tenancies[0]])).toBe('pty_a');
    expect(pickDefaultTenancyId(tenancies)).toBe('');
  });

  it('blocks confirm until tenancy belongs to selected property', () => {
    const form = {
      property_id: 'prop-a',
      expected_amount: '1200',
      start_date: '2026-06-01',
      is_external_payer: false,
      tenancy_id: 'pty_b',
    };
    expect(canConfirmRentSchedule(form, filterTenanciesForProperty(tenancies, 'prop-a'))).toBe(false);
    expect(
      canConfirmRentSchedule(
        { ...form, tenancy_id: 'pty_a' },
        filterTenanciesForProperty(tenancies, 'prop-a'),
      ),
    ).toBe(true);
  });
});
