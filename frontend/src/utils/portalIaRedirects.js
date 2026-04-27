/** Preserve legacy links when tenant delivery moved under /tenants. */
export function complianceTenantDeliveryRedirectTarget(search = '') {
  return `/tenants/delivery${search || ''}`;
}
