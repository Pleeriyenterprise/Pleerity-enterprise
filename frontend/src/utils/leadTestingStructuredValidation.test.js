import {
  LEAD_TESTING_ASSESSMENT_DATE_REQUIRED_MESSAGE,
  LEAD_TESTING_NEXT_REVIEW_REQUIRED_MESSAGE,
  validateLeadTestingStructuredDeclarationFields,
} from './leadTestingStructuredValidation';

describe('validateLeadTestingStructuredDeclarationFields', () => {
  it('passes for a valid payload', () => {
    expect(
      validateLeadTestingStructuredDeclarationFields({
        assessment_completed: { answer: true },
        assessment_date: { answer: '2026-05-05' },
        assessment_type: { answer: 'full_assessment' },
        risk_level: { answer: 'medium' },
        lead_present: { answer: true },
        actions_required: { answer: true },
        actions_taken: { answer: true },
        next_review_date: { answer: '2026-11-05' },
        declaration_confirmed: { answer: true },
      }),
    ).toBeNull();
  });

  it('fails when completed assessment details are missing', () => {
    expect(
      validateLeadTestingStructuredDeclarationFields({
        assessment_completed: { answer: true },
        assessment_date: { answer: '' },
        assessment_type: { answer: 'water_test' },
        risk_level: { answer: 'low' },
        lead_present: { answer: false },
        actions_required: { answer: false },
        declaration_confirmed: { answer: true },
      }),
    ).toBe(LEAD_TESTING_ASSESSMENT_DATE_REQUIRED_MESSAGE);
  });

  it('fails when actions required but next review date missing', () => {
    expect(
      validateLeadTestingStructuredDeclarationFields({
        assessment_completed: { answer: true },
        assessment_date: { answer: '2026-05-05' },
        assessment_type: { answer: 'paint_or_materials' },
        risk_level: { answer: 'high' },
        lead_present: { answer: true },
        actions_required: { answer: true },
        next_review_date: { answer: '' },
        declaration_confirmed: { answer: true },
      }),
    ).toBe(LEAD_TESTING_NEXT_REVIEW_REQUIRED_MESSAGE);
  });

  it('does not affect unrelated workflows payloads', () => {
    expect(
      validateLeadTestingStructuredDeclarationFields({
        declaration_confirmed: { answer: true },
        some_other_workflow_field: { answer: 'value' },
      }),
    ).toBeNull();
  });
});
