/**
 * Display-only mirror of backend/utils/risk_bands.py thresholds.
 * Use for chart bands and static copy only — never infer grade, colour, or message from score.
 */
export const SCORE_BAND_LOW_MIN = 80;
export const SCORE_BAND_MODERATE_MIN = 60;
export const SCORE_BAND_HIGH_MIN = 40;

export const SCORE_CHART_RISK_BANDS = [
  { yMin: 0, yMax: SCORE_BAND_HIGH_MIN - 1, fill: 'rgba(185, 28, 28, 0.08)', label: 'Critical (0-39)' },
  { yMin: SCORE_BAND_HIGH_MIN, yMax: SCORE_BAND_MODERATE_MIN - 1, fill: 'rgba(180, 83, 9, 0.08)', label: 'High risk (40-59)' },
  { yMin: SCORE_BAND_MODERATE_MIN, yMax: SCORE_BAND_LOW_MIN - 1, fill: 'rgba(180, 83, 9, 0.06)', label: 'Moderate risk (60-79)' },
  { yMin: SCORE_BAND_LOW_MIN, yMax: 100, fill: 'rgba(21, 128, 61, 0.05)', label: 'Low risk (80-100)' },
];

export const SCORE_FRAMEWORK_RISK_BANDS_COPY =
  'Risk bands use the same ranges across the portal: 80–100 lower risk; 60–79 Moderate risk; 40–59 high; 0–39 critical.';
