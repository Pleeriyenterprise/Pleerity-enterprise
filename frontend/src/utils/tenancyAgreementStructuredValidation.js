function _answer(fields, id) {
  const node = fields && typeof fields === 'object' ? fields[id] : null;
  return node && typeof node === 'object' ? node.answer : undefined;
}

function _isYes(v) {
  if (typeof v === 'boolean') return v;
  return String(v ?? '').trim().toLowerCase() === 'yes';
}

function _hasValue(v) {
  return !(v == null || String(v).trim() === '');
}

export const TENANCY_AGREEMENT_DECLARATION_REQUIRED_MESSAGE =
  'Confirm that your tenancy agreement declaration is accurate to continue.';
export const TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE =
  'Complete agreement type, tenancy start date, tenant/occupier name, and signed-by-parties when an agreement exists.';

export function validateTenancyAgreementStructuredDeclarationFields(structuredFields) {
  const fields = structuredFields && typeof structuredFields === 'object' ? structuredFields : {};
  if (!_isYes(_answer(fields, 'declaration_confirmed'))) {
    return TENANCY_AGREEMENT_DECLARATION_REQUIRED_MESSAGE;
  }
  if (_isYes(_answer(fields, 'agreement_exists'))) {
    if (!_hasValue(_answer(fields, 'agreement_type'))) return TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE;
    if (!_hasValue(_answer(fields, 'tenancy_start_date'))) return TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE;
    if (!_hasValue(_answer(fields, 'tenant_or_occupier_name'))) return TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE;
    if (_answer(fields, 'signed_by_parties') == null) return TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE;
  }
  return null;
}

