import {
  applyPostcodeLookupResult,
  jurisdictionFromPostcodeLookup,
  postcodeFromSuggestion,
} from './postcodeLookupApply';

describe('postcodeLookupApply', () => {
  it('normalises postcode from autocomplete suggestion', () => {
    expect(postcodeFromSuggestion({ postcode: 'sw1a1aa' })).toBe('SW1A 1AA');
    expect(postcodeFromSuggestion({ outcode: 'KY10', incode: '2AA' })).toBe('KY10 2AA');
  });

  it('maps country to jurisdiction when recognised', () => {
    expect(jurisdictionFromPostcodeLookup({ country: 'Scotland' })).toBe('Scotland');
    expect(jurisdictionFromPostcodeLookup({ country: 'England' })).toBe('England');
    expect(jurisdictionFromPostcodeLookup({ country: 'Greater London' })).toBe('');
  });

  it('fills city and jurisdiction only when empty by default', () => {
    const applied = applyPostcodeLookupResult(
      {
        postcode: 'EH1 1AA',
        suggested_city: 'Edinburgh',
        country: 'Scotland',
      },
      { postcode: 'EH11AA', city: '', jurisdiction: '' }
    );
    expect(applied.postcode).toBe('EH1 1AA');
    expect(applied.city).toBe('Edinburgh');
    expect(applied.jurisdiction).toBe('Scotland');
  });

  it('does not overwrite city when fillOnlyEmpty and city set', () => {
    const applied = applyPostcodeLookupResult(
      { postcode: 'SW1A 1AA', suggested_city: 'London', country: 'England' },
      { city: 'Westminster', jurisdiction: 'Wales' },
      { fillOnlyEmpty: true }
    );
    expect(applied.city).toBeUndefined();
    expect(applied.jurisdiction).toBeUndefined();
  });
});
