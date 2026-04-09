import {
  portfolioHardFallbackNoticeActive,
  portfolioJurisdictionBannerState,
  propertyPageJurisdictionBanners,
} from './jurisdictionUiPolicy';
import { jurisdictionSourceLabel } from './jurisdictionComplianceCopy';

describe('propertyPageJurisdictionBanners', () => {
  it('property_explicit: no banners', () => {
    const r = propertyPageJurisdictionBanners('property_explicit');
    expect(r.showHardWarning).toBe(false);
    expect(r.showSoftAccountDefaultNotice).toBe(false);
  });

  it('client_default: soft notice only', () => {
    const r = propertyPageJurisdictionBanners('client_default');
    expect(r.showHardWarning).toBe(false);
    expect(r.showSoftAccountDefaultNotice).toBe(true);
  });

  it('default_fallback: hard warning only', () => {
    const r = propertyPageJurisdictionBanners('default_fallback');
    expect(r.showHardWarning).toBe(true);
    expect(r.showSoftAccountDefaultNotice).toBe(false);
  });

  it('unknown or null basis: no banners', () => {
    expect(propertyPageJurisdictionBanners(null).showHardWarning).toBe(false);
    expect(propertyPageJurisdictionBanners(undefined).showSoftAccountDefaultNotice).toBe(false);
    expect(propertyPageJurisdictionBanners('').showHardWarning).toBe(false);
  });
});

describe('portfolio hard fallback (Dashboard / Today)', () => {
  it('does not show hard path for client_default-only notice', () => {
    expect(
      portfolioHardFallbackNoticeActive({ active: true, compliance_basis: 'client_default' }),
    ).toBe(false);
  });

  it('does not show hard path when notice inactive even if compliance_basis string present', () => {
    expect(
      portfolioHardFallbackNoticeActive({ active: false, compliance_basis: 'default_fallback' }),
    ).toBe(false);
  });

  it('shows hard path only for active default_fallback notice', () => {
    expect(
      portfolioHardFallbackNoticeActive({ active: true, compliance_basis: 'default_fallback' }),
    ).toBe(true);
  });

  it('banner state ignores hypothetical compliance_confidence (caller must not use it as trigger)', () => {
    const state = portfolioJurisdictionBannerState(
      { active: false, compliance_basis: 'default_fallback' },
      false,
    );
    expect(state.showFull).toBe(false);
    expect(state.showCompact).toBe(false);
  });

  it('compact after acknowledgement', () => {
    const state = portfolioJurisdictionBannerState(
      { active: true, compliance_basis: 'default_fallback' },
      true,
    );
    expect(state.showFull).toBe(false);
    expect(state.showCompact).toBe(true);
  });
});

describe('jurisdiction source labels', () => {
  it('maps API sources to product labels', () => {
    expect(jurisdictionSourceLabel('property_record')).toBe('Property');
    expect(jurisdictionSourceLabel('account_default')).toBe('Account default');
    expect(jurisdictionSourceLabel('system_default')).toBe('Required / System default');
  });
});
