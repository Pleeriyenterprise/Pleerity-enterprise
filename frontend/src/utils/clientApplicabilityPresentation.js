/**
 * Client/runtime applicability presentation helpers (bounded; keep aligned with
 * backend/services/client_applicability_coherence.py).
 */

/** @param {Record<string, unknown>|undefined} requirement */
export function legionellaOperationalApplicabilityReconciled(requirement) {
  const prov = requirement?.applicability_provenance;
  if (!prov || typeof prov !== 'object') return false;
  const rec = prov.operational_applicability_reconciliation;
  return (
    rec &&
    typeof rec === 'object' &&
    rec.source === 'legionella_operational_surfaced_actionable_v1'
  );
}

/** @param {Record<string, unknown>|undefined} requirement */
export function walesOccupationOperationalApplicabilityReconciled(requirement) {
  const prov = requirement?.applicability_provenance;
  if (!prov || typeof prov !== 'object') return false;
  const rec = prov.operational_applicability_reconciliation;
  return (
    rec &&
    typeof rec === 'object' &&
    rec.source === 'wales_occupation_contract_operational_surfaced_actionable_v1'
  );
}

/** @param {Record<string, unknown>|undefined} requirement */
export function scotlandLandlordRegistrationOperationalApplicabilityReconciled(requirement) {
  const prov = requirement?.applicability_provenance;
  if (!prov || typeof prov !== 'object') return false;
  const rec = prov.operational_applicability_reconciliation;
  return (
    rec &&
    typeof rec === 'object' &&
    rec.source === 'scotland_landlord_registration_operational_surfaced_actionable_v1'
  );
}

/** @param {Record<string, unknown>|undefined} requirement */
export function rentSmartWalesOperationalApplicabilityReconciled(requirement) {
  const prov = requirement?.applicability_provenance;
  if (!prov || typeof prov !== 'object') return false;
  const rec = prov.operational_applicability_reconciliation;
  return (
    rec &&
    typeof rec === 'object' &&
    rec.source === 'rent_smart_wales_operational_surfaced_actionable_v1'
  );
}

/** @param {Record<string, unknown>|undefined} requirement */
export function landlordRegistrationNiOperationalApplicabilityReconciled(requirement) {
  const prov = requirement?.applicability_provenance;
  if (!prov || typeof prov !== 'object') return false;
  const rec = prov.operational_applicability_reconciliation;
  return (
    rec &&
    typeof rec === 'object' &&
    rec.source === 'landlord_registration_ni_operational_surfaced_actionable_v1'
  );
}

/** Hide matrix "Mark not applicable" when operational reconciliation is active. */
export function suppressMarkNotApplicableCta(requirement) {
  return (
    legionellaOperationalApplicabilityReconciled(requirement) ||
    walesOccupationOperationalApplicabilityReconciled(requirement) ||
    scotlandLandlordRegistrationOperationalApplicabilityReconciled(requirement) ||
    rentSmartWalesOperationalApplicabilityReconciled(requirement) ||
    landlordRegistrationNiOperationalApplicabilityReconciled(requirement)
  );
}
