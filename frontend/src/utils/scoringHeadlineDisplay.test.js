import {
  headlineScoreDisplayForDashboard,
  headlineScoreShowsOutOf100,
  SCORING_HEADLINE_NO_DATA,
} from './scoringHeadlineDisplay';

describe('scoringHeadlineDisplay Phase 2B presentation', () => {
  it('ACTIVE_PENDING / calculating shows Updating… not a numeric score', () => {
    expect(headlineScoreDisplayForDashboard(80, 'calculating')).toBe('Updating…');
    expect(headlineScoreShowsOutOf100(80, 'calculating')).toBe(false);
  });

  it('PARKED + stored score (stale) shows the numeric score', () => {
    expect(headlineScoreDisplayForDashboard(72, 'stale')).toBe(72);
    expect(headlineScoreShowsOutOf100(72, 'stale')).toBe(true);
  });

  it('PARKED without score (reconciliation_required) is unavailable, not calculating', () => {
    expect(headlineScoreDisplayForDashboard(null, 'reconciliation_required')).toBe(SCORING_HEADLINE_NO_DATA);
    expect(headlineScoreShowsOutOf100(null, 'reconciliation_required')).toBe(false);
  });

  it('CURRENT / ok remains a numeric headline', () => {
    expect(headlineScoreDisplayForDashboard(88, 'ok')).toBe(88);
    expect(headlineScoreShowsOutOf100(88, 'ok')).toBe(true);
  });
});
