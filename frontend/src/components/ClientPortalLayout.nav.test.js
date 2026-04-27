import { PORTAL_TABS } from './ClientPortalLayout';

describe('ClientPortalLayout top navigation', () => {
  it('keeps Tenants and Reports tabs and removes Tenant Delivery tab', () => {
    const labels = PORTAL_TABS.map((t) => t.label);

    expect(labels).toContain('Tenants');
    expect(labels).toContain('Reports');
    expect(labels).not.toContain('Tenant delivery');
  });
});
