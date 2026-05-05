export const LEGIONELLA_DECLARATION_REQUIRED_MESSAGE =
  'Confirm that your Legionella assessment declaration is accurate to continue.';
export const LEGIONELLA_ASSESSMENT_DATE_REQUIRED_MESSAGE =
  'Enter the assessment date when an assessment is completed.';
export const LEGIONELLA_RISK_LEVEL_REQUIRED_MESSAGE =
  'Select the Legionella risk level for the completed assessment.';
export const LEGIONELLA_CONTROL_MEASURES_REQUIRED_MESSAGE =
  'Confirm whether control measures are in place for the completed assessment.';
export const LEGIONELLA_ACTIONS_REQUIRED_MESSAGE =
  'Confirm whether follow-up actions are required for the completed assessment.';
export const LEGIONELLA_NEXT_REVIEW_REQUIRED_MESSAGE =
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

export function validateLegionellaStructuredDeclarationFields(structuredPayload) {
  if (!truthyYes(structuredAnswer(structuredPayload, 'declaration_confirmed'))) {
    return LEGIONELLA_DECLARATION_REQUIRED_MESSAGE;
  }
  const assessmentCompleted = truthyYes(structuredAnswer(structuredPayload, 'assessment_completed'));
  if (assessmentCompleted) {
    if (!nonEmpty(structuredPayload, 'assessment_date')) return LEGIONELLA_ASSESSMENT_DATE_REQUIRED_MESSAGE;
    if (!nonEmpty(structuredPayload, 'risk_level')) return LEGIONELLA_RISK_LEVEL_REQUIRED_MESSAGE;
    if (structuredAnswer(structuredPayload, 'control_measures_in_place') == null) {
      return LEGIONELLA_CONTROL_MEASURES_REQUIRED_MESSAGE;
    }
    if (structuredAnswer(structuredPayload, 'actions_required') == null) return LEGIONELLA_ACTIONS_REQUIRED_MESSAGE;
  }
  const actionsRequired = truthyYes(structuredAnswer(structuredPayload, 'actions_required'));
  if (actionsRequired && !nonEmpty(structuredPayload, 'next_review_date')) {
    return LEGIONELLA_NEXT_REVIEW_REQUIRED_MESSAGE;
  }
  return null;
}
