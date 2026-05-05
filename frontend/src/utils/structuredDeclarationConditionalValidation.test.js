import {
  RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE,
  RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES,
  evaluateStructuredDeclarationConditionalRules,
} from './structuredDeclarationConditionalValidation';

describe('evaluateStructuredDeclarationConditionalRules', () => {
  it('requires follow_up_date when time_limited', () => {
    const payload = {
      right_to_rent_status: { answer: 'time_limited' },
      follow_up_required: { answer: false },
      follow_up_date: { answer: '' },
    };
    expect(
      evaluateStructuredDeclarationConditionalRules(RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES, payload),
    ).toBe(RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE);
  });

  it('requires follow_up_date when follow_up_required is yes', () => {
    const payload = {
      right_to_rent_status: { answer: 'unlimited' },
      follow_up_required: { answer: true },
      follow_up_date: { answer: null },
    };
    expect(
      evaluateStructuredDeclarationConditionalRules(RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES, payload),
    ).toBe(RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE);
  });

  it('passes unlimited and follow_up_required no without follow_up_date', () => {
    const payload = {
      right_to_rent_status: { answer: 'unlimited' },
      follow_up_required: { answer: false },
      follow_up_date: { answer: '' },
    };
    expect(
      evaluateStructuredDeclarationConditionalRules(RIGHT_TO_RENT_STRUCTURED_DECLARATION_CONDITIONAL_RULES, payload),
    ).toBeNull();
  });
});
