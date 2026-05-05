import {
  WALES_OCCUPATION_CONTRACT_DECLARATION_REQUIRED_MESSAGE,
  WALES_OCCUPATION_CONTRACT_ISSUED_FIELD_REQUIRED_MESSAGE,
  validateWalesOccupationContractStructuredDeclarationFields,
} from './walesOccupationContractStructuredValidation';

describe('validateWalesOccupationContractStructuredDeclarationFields', () => {
  it('requires declaration_confirmed', () => {
    expect(
      validateWalesOccupationContractStructuredDeclarationFields({
        occupation_contract_issued: { answer: false },
        declaration_confirmed: { answer: false },
      }),
    ).toBe(WALES_OCCUPATION_CONTRACT_DECLARATION_REQUIRED_MESSAGE);
  });

  it('requires issue fields when issued', () => {
    expect(
      validateWalesOccupationContractStructuredDeclarationFields({
        occupation_contract_issued: { answer: true },
        issue_date: { answer: '' },
        contract_holder_name: { answer: 'A' },
        service_method: { answer: 'email' },
        declaration_confirmed: { answer: true },
      }),
    ).toBe(WALES_OCCUPATION_CONTRACT_ISSUED_FIELD_REQUIRED_MESSAGE);
  });
});
