import {
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
});
