import {
  NAV_TIER,
  PORTAL_PRIMARY_NAV_ITEMS,
  PORTAL_SECONDARY_NAV_ITEMS,
  PORTAL_TABS,
  buildPortalNavigationModel,
  isOperationsPath,
  isSecondaryNavPath,
  isSettingsPath,
} from './portalNavigationConfig';

describe('portalNavigationConfig', () => {
  const allFeatures = () => true;

  it('classifies primary operational items separately from secondary', () => {
    const primaryLabels = PORTAL_PRIMARY_NAV_ITEMS.filter((i) => i.type !== 'group').map((i) => i.label);
    const secondaryLabels = PORTAL_SECONDARY_NAV_ITEMS.map((i) => i.label);

    expect(primaryLabels).toEqual([
      'Today',
      'Command center',
      'Dashboard',
      'Properties',
      'Requirements',
      'Documents',
    ]);
    expect(secondaryLabels).toEqual(['Calendar', 'Reports', 'Tenants', 'Billing', 'Settings']);
    expect(PORTAL_PRIMARY_NAV_ITEMS.every((i) => i.tier === NAV_TIER.PRIMARY || i.type === 'group')).toBe(true);
    expect(PORTAL_SECONDARY_NAV_ITEMS.every((i) => i.tier === NAV_TIER.SECONDARY)).toBe(true);
  });

  it('keeps legacy PORTAL_TABS labels for regression', () => {
    const labels = PORTAL_TABS.map((t) => t.label);
    expect(labels).toContain('Tenants');
    expect(labels).toContain('Reports');
    expect(labels).not.toContain('Tenant delivery');
  });

  it('builds hierarchy model with operations group and filtered secondary', () => {
    const model = buildPortalNavigationModel({
      navHasFeature: allFeatures,
      showReports: true,
      userRole: 'ROLE_CLIENT_ADMIN',
    });

    expect(model.primaryLinks.map((i) => i.label)).toHaveLength(6);
    expect(model.operationsGroup?.label).toBe('Operations');
    expect(model.operationsGroup?.children.length).toBeGreaterThan(0);
    expect(model.secondaryItems.map((i) => i.label)).toEqual([
      'Calendar',
      'Reports',
      'Tenants',
      'Billing',
      'Settings',
    ]);
  });

  it('filters gated secondary items when features are off', () => {
    const model = buildPortalNavigationModel({
      navHasFeature: (key) => key !== 'tenant_portal' && key !== 'invoicing',
      showReports: false,
      userRole: 'ROLE_CLIENT',
    });

    expect(model.secondaryItems.map((i) => i.label)).toEqual(['Calendar', 'Settings']);
  });

  it('detects operations and secondary paths', () => {
    expect(isOperationsPath('/operations/rent')).toBe(true);
    expect(isSecondaryNavPath('/settings/profile')).toBe(true);
    expect(isSecondaryNavPath('/dashboard')).toBe(false);
    expect(isSettingsPath('/settings/billing', { invoicingEnabled: true })).toBe(false);
    expect(isSettingsPath('/settings/profile', { invoicingEnabled: true })).toBe(true);
  });
});
