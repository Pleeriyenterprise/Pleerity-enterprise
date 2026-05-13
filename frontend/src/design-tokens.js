/**
 * Pleerity Enterprise — governed design tokens (frontend).
 * Pleerity Brand v1.0 — single presentation layer; keep aligned with `src/config/branding.js`.
 * @see docs/governance/DESIGN_SYSTEM_GOVERNANCE.md
 */

import branding from './config/branding';

const { colors: bc, surfaces, text, chart } = branding;

/** Hex palette for inline styles, charts, and legacy callers. */
export const colors = {
  navy: bc.primary,
  teal: bc.secondary,
  tealLight: '#ccfbf1',
  tealMuted: 'rgba(0, 184, 169, 0.2)',
  cardBg: surfaces.card,
  pageBg: surfaces.appBackground,
  border: surfaces.border,
  borderSoft: '#F1F5F9',
  textPrimary: text.primary,
  textSecondary: text.secondary,
  success: bc.success,
  successBg: '#f0fdf4',
  warning: bc.warning,
  warningBg: '#fffbeb',
  danger: bc.danger,
  dangerBg: '#fef2f2',
  info: bc.info,
  infoBg: '#eff6ff',
  valid: '#15803d',
  validBg: '#f0fdf4',
  missing: '#b91c1c',
  missingBg: '#fef2f2',
  expiring: '#b45309',
  expiringBg: '#fffbeb',
  overdue: '#b91c1c',
  overdueBg: '#fef2f2',
  failed: '#991b1b',
  failedBg: '#fef2f2',
  riskLow: '#15803d',
  riskMedium: '#b45309',
  riskHigh: '#b91c1c',
  riskCritical: '#7f1d1d',
};

/** Multi-segment chart / donut — Midnight → teal ramp → slate → baseline (no consumer rainbow). */
export const chartDonutPalette = [
  bc.primary,
  '#0f766e',
  bc.secondary,
  chart.trendSecondary,
  chart.baseline,
];

export const chartTokens = chart;

export const spacing = {
  card: '1.5rem',
  cardSm: '1rem',
  section: '2rem',
  page: '2rem',
  header: '1rem',
  navItem: '0.75rem 1rem',
};

export const typography = {
  fontFamily: 'inherit',
  fontHeading: branding.typography.fontHeading,
  fontBody: branding.typography.fontBody,
  h1: '1.875rem',
  h2: '1.5rem',
  h3: '1.125rem',
  body: '1rem',
  bodySm: '0.875rem',
  caption: '0.75rem',
};

export const borderRadius = {
  card: '0.75rem',
  button: '0.5rem',
  chip: '9999px',
};
