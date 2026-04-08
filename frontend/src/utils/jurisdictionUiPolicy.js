/**
 * Product rules for jurisdiction UI (aligned with backend compliance_basis / notice).
 * Hard amber warnings only for true default_fallback — not for client_default portfolios.
 */

/** @param {string|null|undefined} complianceBasis property_explicit | client_default | default_fallback */
export function propertyPageJurisdictionBanners(complianceBasis) {
  const basis = complianceBasis ?? null;
  const showHardWarning = basis === 'default_fallback';
  const showSoftAccountDefaultNotice = basis === 'client_default';
  return { showHardWarning, showSoftAccountDefaultNotice };
}

/** True only when portfolio notice indicates at least one property uses system default (not account default). */
export function portfolioHardFallbackNoticeActive(jurisdictionComplianceNotice) {
  const n = jurisdictionComplianceNotice;
  return Boolean(n && n.active === true && n.compliance_basis === 'default_fallback');
}

/**
 * Dashboard / Today full vs compact amber banner (after user acknowledges fallback).
 * Do not pass compliance_confidence here — not a trigger for this banner.
 */
export function portfolioJurisdictionBannerState(jurisdictionComplianceNotice, jurisdictionFallbackAcknowledged) {
  const noticeActive = portfolioHardFallbackNoticeActive(jurisdictionComplianceNotice);
  const acked = jurisdictionFallbackAcknowledged === true;
  return {
    showFull: noticeActive && !acked,
    showCompact: noticeActive && acked,
  };
}
