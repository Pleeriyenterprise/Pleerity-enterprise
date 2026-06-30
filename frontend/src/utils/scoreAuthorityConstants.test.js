import {
  SCORE_BAND_HIGH_MIN,
  SCORE_BAND_LOW_MIN,
  SCORE_BAND_MODERATE_MIN,
  SCORE_CHART_RISK_BANDS,
} from './scoreAuthorityConstants';

describe('scoreAuthorityConstants', () => {
  it('mirrors backend threshold boundaries', () => {
    expect(SCORE_BAND_LOW_MIN).toBe(80);
    expect(SCORE_BAND_MODERATE_MIN).toBe(60);
    expect(SCORE_BAND_HIGH_MIN).toBe(40);
  });

  it('chart bands align to canonical ranges without overlap gaps', () => {
    expect(SCORE_CHART_RISK_BANDS[0].yMax).toBe(39);
    expect(SCORE_CHART_RISK_BANDS[1].yMin).toBe(40);
    expect(SCORE_CHART_RISK_BANDS[2].yMin).toBe(60);
    expect(SCORE_CHART_RISK_BANDS[3].yMin).toBe(80);
    expect(SCORE_CHART_RISK_BANDS[3].yMax).toBe(100);
  });
});
