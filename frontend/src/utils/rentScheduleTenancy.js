/**
 * Rent schedule setup — property-scoped tenancy selection helpers.
 */

/**
 * @param {Array<Record<string, unknown>>} tenancies
 * @param {string} propertyId
 */
export function filterTenanciesForProperty(tenancies, propertyId) {
  if (!propertyId) return [];
  return (tenancies || []).filter((t) => String(t.property_id || '') === String(propertyId));
}

/**
 * @param {string} tenancyId
 * @param {Array<Record<string, unknown>>} tenancies
 * @param {string} propertyId
 */
export function tenancyBelongsToProperty(tenancyId, tenancies, propertyId) {
  if (!tenancyId || !propertyId) return false;
  return filterTenanciesForProperty(tenancies, propertyId).some(
    (t) => String(t.tenancy_id) === String(tenancyId),
  );
}

/**
 * @param {Record<string, unknown>} form
 * @param {Array<Record<string, unknown>>} scopedTenancies
 * @param {boolean|null|undefined} tenancyBackendReady
 */
export function canConfirmRentSchedule(form, scopedTenancies, tenancyBackendReady = true) {
  if (!form?.property_id || !form?.expected_amount || !form?.start_date) return false;
  if (tenancyBackendReady === false) return false;
  if (form.is_external_payer) {
    return Boolean(String(form.external_payer_name || '').trim());
  }
  return tenancyBelongsToProperty(form.tenancy_id, scopedTenancies, form.property_id);
}

/**
 * @param {Array<Record<string, unknown>>} scopedTenancies
 */
export function pickDefaultTenancyId(scopedTenancies) {
  const active = (scopedTenancies || []).filter((t) =>
    ['active', 'ending_soon'].includes(String(t.status || '').toLowerCase()),
  );
  if (active.length === 1) return active[0].tenancy_id;
  return '';
}
