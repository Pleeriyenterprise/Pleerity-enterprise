import {
  TENANCY_AGREEMENT_DECLARATION_REQUIRED_MESSAGE,
  TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE,
  validateTenancyAgreementStructuredDeclarationFields,
} from './tenancyAgreementStructuredValidation';

describe('validateTenancyAgreementStructuredDeclarationFields', () => {
  it('requires declaration confirmation', () => {
    expect(
      validateTenancyAgreementStructuredDeclarationFields({
        agreement_exists: { answer: true },
        declaration_confirmed: { answer: false },
      }),
    ).toBe(TENANCY_AGREEMENT_DECLARATION_REQUIRED_MESSAGE);
  });

  it('requires detail fields when agreement exists', () => {
    expect(
      validateTenancyAgreementStructuredDeclarationFields({
        agreement_exists: { answer: true },
        agreement_type: { answer: '' },
        tenancy_start_date: { answer: '2026-04-01' },
        tenant_or_occupier_name: { answer: 'Tenant One' },
        signed_by_parties: { answer: true },
        declaration_confirmed: { answer: true },
      }),
    ).toBe(TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE);
  });
});

