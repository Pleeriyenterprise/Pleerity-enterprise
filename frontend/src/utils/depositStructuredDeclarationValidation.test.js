import {
  DEPOSIT_DECLARATION_CONFIRMATION_REQUIRED_MESSAGE,
  DEPOSIT_PRESCRIBED_INFO_FIELD_REQUIRED_MESSAGE,
  validateDepositStructuredDeclarationFields,
} from './depositStructuredDeclarationValidation';

describe('validateDepositStructuredDeclarationFields', () => {
  it('requires declaration_confirmed', () => {
    expect(
      validateDepositStructuredDeclarationFields({
        deposit_taken: { answer: false },
        prescribed_information_served: { answer: false },
        declaration_confirmed: { answer: false },
      }),
    ).toBe(DEPOSIT_DECLARATION_CONFIRMATION_REQUIRED_MESSAGE);
  });

  it('requires PI fields when served', () => {
    expect(
      validateDepositStructuredDeclarationFields({
        deposit_taken: { answer: false },
        prescribed_information_served: { answer: true },
        prescribed_information_served_date: { answer: '' },
        served_to: { answer: 'A' },
        service_method: { answer: 'email' },
        declaration_confirmed: { answer: true },
      }),
    ).toBe(DEPOSIT_PRESCRIBED_INFO_FIELD_REQUIRED_MESSAGE);
  });
});
