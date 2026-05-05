import {
  LEGIONELLA_ASSESSMENT_DATE_REQUIRED_MESSAGE,
  LEGIONELLA_NEXT_REVIEW_REQUIRED_MESSAGE,
  validateLegionellaStructuredDeclarationFields,
} from './legionellaStructuredValidation';

describe('validateLegionellaStructuredDeclarationFields', () => {
  it('requires assessment_date when assessment is completed', () => {
    expect(
      validateLegionellaStructuredDeclarationFields({
        assessment_completed: { answer: true },
        assessment_date: { answer: '' },
        risk_level: { answer: 'medium' },
        control_measures_in_place: { answer: true },
        actions_required: { answer: false },
        declaration_confirmed: { answer: true },
      }),
    ).toBe(LEGIONELLA_ASSESSMENT_DATE_REQUIRED_MESSAGE);
  });

  it('requires next_review_date when actions_required', () => {
    expect(
      validateLegionellaStructuredDeclarationFields({
        assessment_completed: { answer: true },
        assessment_date: { answer: '2026-05-05' },
        risk_level: { answer: 'high' },
        control_measures_in_place: { answer: true },
        actions_required: { answer: true },
        next_review_date: { answer: '' },
        declaration_confirmed: { answer: true },
      }),
    ).toBe(LEGIONELLA_NEXT_REVIEW_REQUIRED_MESSAGE);
  });
});
