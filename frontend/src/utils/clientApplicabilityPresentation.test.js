import {
  landlordRegistrationNiOperationalApplicabilityReconciled,
  scotlandLandlordRegistrationOperationalApplicabilityReconciled,
  suppressMarkNotApplicableCta,
} from './clientApplicabilityPresentation';

describe('clientApplicabilityPresentation', () => {
  it('detects Scotland landlord registration operational reconciliation', () => {
    const row = {
      applicability_provenance: {
        operational_applicability_reconciliation: {
          source: 'scotland_landlord_registration_operational_surfaced_actionable_v1',
        },
      },
    };
    expect(scotlandLandlordRegistrationOperationalApplicabilityReconciled(row)).toBe(true);
    expect(suppressMarkNotApplicableCta(row)).toBe(true);
  });

  it('detects NI landlord registration operational reconciliation', () => {
    const row = {
      applicability_provenance: {
        operational_applicability_reconciliation: {
          source: 'landlord_registration_ni_operational_surfaced_actionable_v1',
        },
      },
    };
    expect(landlordRegistrationNiOperationalApplicabilityReconciled(row)).toBe(true);
    expect(suppressMarkNotApplicableCta(row)).toBe(true);
  });
});
