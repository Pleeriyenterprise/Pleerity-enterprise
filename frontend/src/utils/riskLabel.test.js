import {
  formatRiskLabel,
  getRiskBandExplanation,
  resolveScorePresentationFields,
} from './riskLabel';

describe('score authority presentation (API-only)', () => {
  const apiPayload = {
    grade: 'C',
    color: 'amber',
    message: 'Moderate risk - action required',
    band_explanation: 'Moderate risk (60–79): Action required to maintain compliance.',
    risk_level: 'Moderate Risk',
  };

  it('formatRiskLabel uses Moderate risk not Medium risk', () => {
    expect(formatRiskLabel('Moderate Risk')).toBe('Moderate risk');
    expect(formatRiskLabel('medium risk')).toBe('Moderate risk');
    expect(formatRiskLabel('Moderate risk')).toBe('Moderate risk');
  });

  it('resolveScorePresentationFields prefers primary API payload', () => {
    const merged = resolveScorePresentationFields(apiPayload, { grade: 'F' });
    expect(merged.grade).toBe('C');
    expect(merged.color).toBe('amber');
    expect(merged.message).toContain('Moderate risk');
  });

  it('getRiskBandExplanation reads band_explanation from API only', () => {
    expect(getRiskBandExplanation(apiPayload)).toContain('Moderate risk (60–79)');
    expect(getRiskBandExplanation({ score: 62 })).toBe('');
  });
});
