/**
 * Compliance Vault Pro – design tokens.
 * Aligned with Pleerity brand: primary #0B1D3A, secondary #00B8A9.
 * @see src/config/branding.js for canonical brand values.
 */

export const colors = {
  // Brand (official Pleerity)
  navy: '#0B1D3A',
  teal: '#00B8A9',
  tealLight: '#ccfbf1',
  tealMuted: 'rgba(0, 184, 169, 0.2)',
  // Surfaces
  cardBg: '#ffffff',
  pageBg: '#f8fafc',
  border: '#e2e8f0',
  borderSoft: '#f1f5f9',
  // Semantic / status (brand-aligned where applicable)
  success: '#10B981',
  successBg: '#f0fdf4',
  warning: '#F59E0B',
  warningBg: '#fffbeb',
  danger: '#EF4444',
  dangerBg: '#fef2f2',
  info: '#3B82F6',
  infoBg: '#eff6ff',
  // Evidence / risk (no legal verdict)
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
  // Risk levels
  riskLow: '#15803d',
  riskMedium: '#b45309',
  riskHigh: '#b91c1c',
  riskCritical: '#7f1d1d',
};

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
  // Headers
  h1: '1.875rem',   // 30px
  h2: '1.5rem',     // 24px
  h3: '1.125rem',   // 18px
  // Body
  body: '1rem',
  bodySm: '0.875rem',
  caption: '0.75rem',
};

export const borderRadius = {
  card: '0.75rem',
  button: '0.5rem',
  chip: '9999px',
};
