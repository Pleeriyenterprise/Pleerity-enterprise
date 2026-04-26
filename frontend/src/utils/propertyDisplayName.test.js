import { getPropertyDisplayName } from './propertyDisplayName';

describe('getPropertyDisplayName', () => {
  it('prefers explicit nickname/name', () => {
    expect(getPropertyDisplayName({ nickname: 'My Flat', address_line_1: '10 Test St' })).toBe('My Flat');
    expect(getPropertyDisplayName({ name: 'Portfolio Home', address_line_1: '10 Test St' })).toBe('Portfolio Home');
  });

  it('falls back to short address and city', () => {
    expect(getPropertyDisplayName({ address_line_1: '10 Test St', city: 'Glasgow' })).toBe('10 Test St, Glasgow');
  });

  it('returns Unnamed property when no usable fields', () => {
    expect(getPropertyDisplayName({})).toBe('Unnamed property');
    expect(getPropertyDisplayName(null)).toBe('Unnamed property');
  });
});

