/**
 * Pleerity branding – single source of truth for frontend.
 * Use this for asset paths, copy, and semantic colors. Keep Tailwind/index.css aligned.
 * Charts/analytics palette: compliant=success, expiring=warning, overdue=danger, trend=secondary, baseline=neutral grey.
 */

export const branding = {
  companyName: 'Pleerity Enterprise Ltd',
  productName: 'Compliance Vault Pro',
  tagline: 'AI-Driven Solutions & Compliance',

  colors: {
    primary: '#0B1D3A',
    secondary: '#00B8A9',
    success: '#10B981',
    warning: '#F59E0B',
    danger: '#EF4444',
    info: '#3B82F6',
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
};

/** For use in img src (same as branding.logoUrl). */
export const BRAND_LOGO_URL = branding.logoUrl;
export const BRAND_FAVICON_URL = branding.faviconUrl;
/** OG/social image; use fallback if og-default.png not in /branding. */
export const BRAND_OG_IMAGE_URL = branding.ogImageUrlFallback;

/** Site URL for canonical/og (no trailing slash). */
export const SITE_URL = 'https://pleerity.com';

/** Support email – prefer config.js REACT_APP for overrides. */
export const SUPPORT_EMAIL = process.env.REACT_APP_SUPPORT_EMAIL || 'info@pleerityenterprise.co.uk';

/** Schema/SEO logo URL (absolute). */
export const SCHEMA_LOGO_URL = `${SITE_URL}/branding/pleerity-logo.png`;

export default branding;
