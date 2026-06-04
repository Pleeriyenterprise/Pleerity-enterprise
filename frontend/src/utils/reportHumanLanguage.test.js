import {
  humanScoreStatusLabel,
  containsInternalLanguageLeak,
  LIVE_EXPORT_DISCLOSURE,
} from './reportHumanLanguage';

describe('reportHumanLanguage', () => {
  it('maps calculating to Score updating', () => {
    expect(humanScoreStatusLabel('calculating')).toBe('Score updating');
  });

  it('detects internal enum leakage', () => {
    expect(containsInternalLanguageLeak('SATISFIED_UNVERIFIED')).toBe(true);
    expect(containsInternalLanguageLeak('Recorded on file')).toBe(false);
  });

  it('live export disclosure avoids implementation tokens', () => {
    expect(LIVE_EXPORT_DISCLOSURE).not.toMatch(/live_regenerated/i);
    expect(LIVE_EXPORT_DISCLOSURE).toMatch(/latest portfolio/i);
  });
});
