import { CLIENT_PATH_PREFIXES, isClientPortalPath } from './clientLoginRedirect';

describe('client login redirect path detection', () => {
  it('includes tenants and reports prefixes for nested IA routes', () => {
    expect(CLIENT_PATH_PREFIXES).toContain('/tenants');
    expect(CLIENT_PATH_PREFIXES).toContain('/reports');
  });

  it('treats /tenants/delivery as a client portal path', () => {
    expect(isClientPortalPath('/tenants/delivery')).toBe(true);
  });

  it('treats /reports/audit-pack as a client portal path', () => {
    expect(isClientPortalPath('/reports/audit-pack')).toBe(true);
  });
});
