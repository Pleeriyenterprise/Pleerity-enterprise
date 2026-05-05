/** Keep messages aligned with backend compliance_evidence_record_service deposit validators. */

export const DEPOSIT_DECLARATION_CONFIRMATION_REQUIRED_MESSAGE =
  'Confirm that your deposit compliance declaration is accurate to continue.';
export const DEPOSIT_PROTECTION_FIELD_REQUIRED_MESSAGE =
  'Complete all deposit protection fields when a deposit is taken.';
export const DEPOSIT_PROTECTION_CONFIRM_REQUIRED_MESSAGE =
  'Confirm that the deposit is protected in an approved scheme when a deposit is taken.';
export const DEPOSIT_PRESCRIBED_INFO_FIELD_REQUIRED_MESSAGE =
  'Complete prescribed information service details when you confirm information was served.';

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

/**
 * @param {Record<string, { answer?: unknown }>} structuredPayload
 * @returns {string|null}
 */
export function validateDepositStructuredDeclarationFields(structuredPayload) {
  if (!truthyYes(structuredAnswer(structuredPayload, 'declaration_confirmed'))) {
    return DEPOSIT_DECLARATION_CONFIRMATION_REQUIRED_MESSAGE;
  }
  const depositTaken = truthyYes(structuredAnswer(structuredPayload, 'deposit_taken'));
  if (depositTaken) {
    for (const fid of [
      'deposit_amount',
      'deposit_received_date',
      'scheme_name',
      'scheme_reference',
      'protection_date',
    ]) {
      if (!nonEmpty(structuredPayload, fid)) return DEPOSIT_PROTECTION_FIELD_REQUIRED_MESSAGE;
    }
    if (!truthyYes(structuredAnswer(structuredPayload, 'protection_confirmed'))) {
      return DEPOSIT_PROTECTION_CONFIRM_REQUIRED_MESSAGE;
    }
  }
  const served = truthyYes(structuredAnswer(structuredPayload, 'prescribed_information_served'));
  if (served) {
    for (const fid of ['prescribed_information_served_date', 'served_to', 'service_method']) {
      if (!nonEmpty(structuredPayload, fid)) return DEPOSIT_PRESCRIBED_INFO_FIELD_REQUIRED_MESSAGE;
    }
  }
  return null;
}
