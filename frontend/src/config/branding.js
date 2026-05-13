/**
 * Pleerity branding – single source of truth for frontend.
 * Use this for asset paths, copy, and semantic colors. Keep Tailwind/index.css aligned.
 * Charts/analytics palette: compliant=success, expiring=warning, overdue=danger, trend=secondary, baseline=neutral grey.
 */

/** Support email – prefer REACT_APP_SUPPORT_EMAIL for overrides. */
export const SUPPORT_EMAIL = process.env.REACT_APP_SUPPORT_EMAIL || 'info@pleerityenterprise.co.uk';

export const branding = {
  companyName: 'Pleerity Enterprise Ltd',
  productName: 'Compliance Vault Pro',
  tagline: 'AI-Driven Solutions & Compliance',
  /** Pleerity Brand v1.0 — do not drift without updating `docs/governance/DESIGN_SYSTEM_GOVERNANCE.md`. */
  brandVersion: '1.0',

  colors: {
    /** Midnight Blue — nav, headers, framework (not default CTA fill; see Button). */
    primary: '#0B1D3A',
    /** Electric Teal — CTAs, links, active states, score highlights. */
    secondary: '#00B8A9',
    success: '#10B981',
    warning: '#F59E0B',
    danger: '#EF4444',
    info: '#3B82F6',
  },

  /** Surfaces & neutrals (enterprise SaaS canvas). */
  surfaces: {
    appBackground: '#F8FAFC',
    card: '#FFFFFF',
    border: '#E5E7EB',
  },

  text: {
    primary: '#111827',
    secondary: '#6B7280',
  },

  /** Charts / analytics — trend primary = teal; do not imply legal outcome. */
  chart: {
    scoreCompliant: '#10B981',
    scoreWarning: '#F59E0B',
    scoreCritical: '#EF4444',
    trendPrimary: '#00B8A9',
    trendSecondary: '#64748B',
    baseline: '#E5E7EB',
  },

  typography: {
    fontHeading: 'Montserrat',
    fontBody: 'Inter',
  },

  /** Base path for brand assets (public folder). No trailing slash. */
  assetsBase: '/branding',
  get logoUrl() {
    return `${this.assetsBase}/pleerity-logo.png`;
  },
  get faviconUrl() {
    return `${this.assetsBase}/favicon.png`;
  },
  get ogImageUrl() {
    return `${this.assetsBase}/og-default.png`;
  },
  /** Fallback when og-default.png not present (e.g. use logo). */
  get ogImageUrlFallback() {
    return `${this.assetsBase}/pleerity-logo.png`;
  },
  /** Customer-facing support / assisted-upload destination (same as SUPPORT_EMAIL). */
  get supportEmail() {
    return SUPPORT_EMAIL;
  },
};

/** For use in img src (same as branding.logoUrl). */
export const BRAND_LOGO_URL = branding.logoUrl;
export const BRAND_FAVICON_URL = branding.faviconUrl;
/** OG/social image; use fallback if og-default.png not in /branding. */
export const BRAND_OG_IMAGE_URL = branding.ogImageUrlFallback;

/** Site URL for canonical/og (no trailing slash). Use custom domain. */
export const SITE_URL = 'https://pleerityenterprise.co.uk';

/** Schema/SEO logo URL (absolute). */
export const SCHEMA_LOGO_URL = `${SITE_URL}/branding/pleerity-logo.png`;

export default branding;
