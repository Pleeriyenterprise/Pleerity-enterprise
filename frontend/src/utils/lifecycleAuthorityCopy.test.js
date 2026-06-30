import { calendarOverdueSubline, riskSignalPresentationHeadline } from './lifecycleAuthorityCopy';

describe('calendarOverdueSubline', () => {
  it('does not imply legal breach', () => {
    expect(calendarOverdueSubline(null)).toMatch(/not a legal compliance verdict/);
  });
});

describe('riskSignalPresentationHeadline', () => {
  it('prefers server label when provided', () => {
    expect(riskSignalPresentationHeadline({ risk_type_label_client: 'Electrical certificate attention' })).toBe(
      'Electrical certificate attention',
    );
  });

  it('uses operational fallback instead of breach language', () => {
    expect(riskSignalPresentationHeadline({ category: 'operational' })).toBe('Operational follow-up suggested');
  });
});
