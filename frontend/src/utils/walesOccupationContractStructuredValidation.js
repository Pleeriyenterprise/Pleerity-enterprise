export const WALES_OCCUPATION_CONTRACT_DECLARATION_REQUIRED_MESSAGE =
  'Confirm that your Wales occupation contract declaration is accurate to continue.';
export const WALES_OCCUPATION_CONTRACT_ISSUED_FIELD_REQUIRED_MESSAGE =
  'Complete issue date, contract-holder name, and service method when the occupation contract is issued.';

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

export function validateWalesOccupationContractStructuredDeclarationFields(structuredPayload) {
  if (!truthyYes(structuredAnswer(structuredPayload, 'declaration_confirmed'))) {
    return WALES_OCCUPATION_CONTRACT_DECLARATION_REQUIRED_MESSAGE;
  }
  const issued = truthyYes(structuredAnswer(structuredPayload, 'occupation_contract_issued'));
  if (issued) {
    for (const fid of ['issue_date', 'contract_holder_name', 'service_method']) {
      if (!nonEmpty(structuredPayload, fid)) return WALES_OCCUPATION_CONTRACT_ISSUED_FIELD_REQUIRED_MESSAGE;
    }
  }
  return null;
}
