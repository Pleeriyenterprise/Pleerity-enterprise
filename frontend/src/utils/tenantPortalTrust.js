/**
 * Trust-first tenant portal helpers — copy, reassurance, and light guidance only.
 * Certificate `type` values align with backend requirement_type (e.g. gas_safety, eicr).
 */

const CRITICAL_TYPES = new Set([
  'gas_safety',
  'eicr',
  'fire_alarm',
  'smoke_co_alarm',
  'fire_risk',
]);

export function hasOverdueCritical(certificates) {
  return (certificates || []).some(
    (c) => c.status === 'OVERDUE' && CRITICAL_TYPES.has(String(c.type || '').toLowerCase())
  );
}

export function hasMultipleOverdue(certificates) {
  return (certificates || []).filter((c) => c.status === 'OVERDUE').length >= 2;
}

/**
 * @param {Array<{ status?: string, type?: string }>} certificates
 * @returns {'request_certificate' | 'contact_landlord' | null}
 */
export function getTenantRecommendedAction(certificates) {
  if (hasOverdueCritical(certificates)) return 'request_certificate';
  if (hasMultipleOverdue(certificates)) return 'contact_landlord';
  return null;
}

export function propertyHasOverdueCertificate(property) {
  return (property?.certificates || []).some((c) => c.status === 'OVERDUE');
}

export function dashboardHasAnyOverdue(properties) {
  return (properties || []).some((p) => propertyHasOverdueCertificate(p));
}

/**
 * Banner tier for the tenant dashboard reassurance strip.
 * `status_gap` = property compliance is AMBER/RED but no certificate row is OVERDUE (sync / rounding / summary lag).
 */
export function getDashboardReassuranceState(properties) {
  if (dashboardHasAnyOverdue(properties)) {
    return { kind: 'overdue' };
  }
  const hasAmberOrRed = (properties || []).some(
    (p) => p.compliance_status === 'AMBER' || p.compliance_status === 'RED'
  );
  if (hasAmberOrRed) {
    return { kind: 'status_gap' };
  }
  return { kind: 'all_clear' };
}

export const TENANT_RECOMMENDED_ACTION_LABEL = {
  request_certificate: 'Request certificate update',
  contact_landlord: 'Contact your landlord',
};

export function formatCertStatusLabel(status) {
  if (!status) return '';
  return String(status).replace(/_/g, ' ');
}

export function getCertificateResponsibilityHint(status) {
  if (status === 'OVERDUE') {
    return "This is your landlord's responsibility. No action is required from you.";
  }
  if (status === 'EXPIRING_SOON') {
    return 'This will need renewal soon. Your landlord is expected to handle this.';
  }
  return null;
}
