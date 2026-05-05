export const LEAD_TESTING_DECLARATION_REQUIRED_MESSAGE =
  'Confirm that your lead risk assessment declaration is accurate to continue.';
export const LEAD_TESTING_ASSESSMENT_DATE_REQUIRED_MESSAGE =
  'Enter the assessment date when an assessment is completed.';
export const LEAD_TESTING_ASSESSMENT_TYPE_REQUIRED_MESSAGE =
  'Select the assessment type for the completed lead assessment.';
export const LEAD_TESTING_RISK_LEVEL_REQUIRED_MESSAGE =
  'Select the lead risk level for the completed assessment.';
export const LEAD_TESTING_LEAD_PRESENT_REQUIRED_MESSAGE =
  'Confirm whether lead is present for the completed assessment.';
export const LEAD_TESTING_ACTIONS_REQUIRED_MESSAGE =
  'Confirm whether follow-up actions are required for the completed assessment.';
export const LEAD_TESTING_NEXT_REVIEW_REQUIRED_MESSAGE =
  'Enter the next review date when actions are required.';

function truthyYes(value) {
  if (value === true) return true;
  if (typeof value === 'string') {
    const u = value.trim().toUpperCase();
    return ['YES', 'TRUE', '1', 'Y'].includes(u);
  }
  return false;
}

function structuredAnswer(structuredPayload, fieldId) {
  if (!structuredPayload || typeof structuredPayload !== 'object') return null;
  const row = structuredPayload[fieldId];
  if (row && typeof row === 'object' && 'answer' in row) return row.answer;
  return null;
}

function nonEmpty(structuredPayload, fieldId) {
  const v = structuredAnswer(structuredPayload, fieldId);
  if (v == null) return false;
  if (typeof v === 'string') return v.trim() !== '';
  if (typeof v === 'number' && Number.isFinite(v)) return true;
  return true;
}

export function validateLeadTestingStructuredDeclarationFields(structuredPayload) {
  if (!truthyYes(structuredAnswer(structuredPayload, 'declaration_confirmed'))) {
    return LEAD_TESTING_DECLARATION_REQUIRED_MESSAGE;
  }
  const assessmentCompleted = truthyYes(structuredAnswer(structuredPayload, 'assessment_completed'));
  if (assessmentCompleted) {
    if (!nonEmpty(structuredPayload, 'assessment_date')) return LEAD_TESTING_ASSESSMENT_DATE_REQUIRED_MESSAGE;
    if (!nonEmpty(structuredPayload, 'assessment_type')) return LEAD_TESTING_ASSESSMENT_TYPE_REQUIRED_MESSAGE;
    if (!nonEmpty(structuredPayload, 'risk_level')) return LEAD_TESTING_RISK_LEVEL_REQUIRED_MESSAGE;
    if (structuredAnswer(structuredPayload, 'lead_present') == null) return LEAD_TESTING_LEAD_PRESENT_REQUIRED_MESSAGE;
    if (structuredAnswer(structuredPayload, 'actions_required') == null) return LEAD_TESTING_ACTIONS_REQUIRED_MESSAGE;
  }
  const actionsRequired = truthyYes(structuredAnswer(structuredPayload, 'actions_required'));
  if (actionsRequired && !nonEmpty(structuredPayload, 'next_review_date')) {
    return LEAD_TESTING_NEXT_REVIEW_REQUIRED_MESSAGE;
  }
  return null;
}
