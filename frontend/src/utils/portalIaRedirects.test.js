import { complianceTenantDeliveryRedirectTarget } from './portalIaRedirects';

describe('portal IA redirects', () => {
  it('redirects legacy tenant delivery path to /tenants/delivery', () => {
    expect(complianceTenantDeliveryRedirectTarget('')).toBe('/tenants/delivery');
  });

  it('preserves query string for legacy tenant delivery links', () => {
    expect(complianceTenantDeliveryRedirectTarget('?property_id=p1')).toBe('/tenants/delivery?property_id=p1');
  });
});
