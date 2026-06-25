/**
 * Lifecycle-aware confirm helpers for DocumentsPage.
 */

const DATE_FIELD_IDS = new Set([
  'expiry_date',
  'issue_date',
  'assessment_date',
  'next_review_date',
  'protection_date',
  'served_date',
  'event_date',
  'tenancy_start_date',
  'fixed_term_end_date',
  'check_date',
  'follow_up_date',
  'completion_date',
  'deposit_received_date',
  'delivery_date',
]);

const DEFAULT_FIELD_LABELS = {
  expiry_date: 'Expiry date',
  issue_date: 'Issue date',
  assessment_date: 'Assessment date',
  next_review_date: 'Next review date',
  protection_date: 'Protection date',
  served_date: 'Served date',
  event_date: 'Event date',
  tenancy_start_date: 'Tenancy start date',
  fixed_term_end_date: 'Fixed term end date',
  check_date: 'Check date',
  follow_up_date: 'Follow-up date',
  completion_date: 'Completion date',
  certificate_number: 'Certificate number',
  licence_number: 'Licence number',
  scheme_name: 'Scheme name',
  scheme_reference: 'Scheme reference',
  deposit_amount: 'Deposit amount',
  served_to: 'Served to',
  service_method: 'Service method',
  guide_version: 'Guide version',
  event_type: 'Event type',
  completion_notes: 'Completion notes',
  installer_name: 'Installer name',
  tenant_name: 'Tenant name',
  agreement_type: 'Agreement type',
  rent_amount: 'Rent amount',
  document_type: 'Document type',
  right_to_rent_status: 'Right to rent status',
  responsible_person: 'Responsible person',
  work_summary: 'Work summary',
  registration_number: 'Registration number',
  issuing_authority: 'Issuing authority',
  registration_status: 'Registration status',
  risk_level: 'Risk level',
};

export function isLifecycleConfirmContractPresent(contract) {
  return Boolean(
    contract &&
      typeof contract === 'object' &&
      Array.isArray(contract.confirm_fields) &&
      contract.lifecycle_semantics,
  );
}

export function getConfirmFieldIds(contract) {
  if (!isLifecycleConfirmContractPresent(contract)) return [];
  const required = contract.confirm_fields || [];
  const optional = contract.optional_fields || [];
  return [...required, ...optional];
}

export function fieldLabel(contract, fieldId) {
  const fromContract = contract?.field_labels?.[fieldId];
  if (fromContract) return fromContract;
  return DEFAULT_FIELD_LABELS[fieldId] || fieldId.replace(/_/g, ' ');
}

export function isDateField(fieldId) {
  return DATE_FIELD_IDS.has(fieldId);
}

export function isFieldForbidden(contract, fieldId) {
  const forbidden = new Set(contract?.forbidden_fields || []);
  return forbidden.has(fieldId);
}

export function initialFormValuesFromExtraction(contract, extractionData = {}) {
  const values = {};
  if (!isLifecycleConfirmContractPresent(contract)) return values;
  const data = extractionData || {};
  for (const fieldId of getConfirmFieldIds(contract)) {
    if (isFieldForbidden(contract, fieldId)) continue;
    const raw = data[fieldId];
    if (raw == null || raw === '') continue;
    values[fieldId] = String(raw).slice(0, 10);
  }
  if (contract.lifecycle_semantics === 'EXPIRY_BASED' && data.expiry_date && !values.expiry_date) {
    values.expiry_date = String(data.expiry_date).slice(0, 10);
  }
  return values;
}

export function buildLifecycleConfirmPayload(contract, formValues) {
  if (!isLifecycleConfirmContractPresent(contract)) return {};
  const forbidden = new Set(contract.forbidden_fields || []);
  const allowed = new Set(getConfirmFieldIds(contract));
  const payload = {};
  for (const [key, value] of Object.entries(formValues || {})) {
    if (!allowed.has(key) || forbidden.has(key)) continue;
    const trimmed = typeof value === 'string' ? value.trim() : value;
    if (trimmed === '' || trimmed == null) continue;
    payload[key] = trimmed;
  }
  return payload;
}

export function contractShowsExpiryField(contract) {
  if (!isLifecycleConfirmContractPresent(contract)) return true;
  if (contract.lifecycle_semantics === 'EXPIRY_BASED') return true;
  return !isFieldForbidden(contract, 'expiry_date');
}

/** Map lifecycle 422 violation list to fieldId → message for form display. */
export function mapLifecycleViolationsToFieldErrors(violations) {
  const out = {};
  if (!Array.isArray(violations)) return out;
  for (const v of violations) {
    if (!v || typeof v !== 'object') continue;
    const field = v.field;
    if (!field || field === '*') continue;
    const message = typeof v.message === 'string' ? v.message : v.code || 'Invalid value';
    out[field] = message;
  }
  return out;
}

/** Extract lifecycle confirm 422 payload from FastAPI error detail. */
export function parseLifecycleConfirm422Detail(err) {
  const raw = err?.response?.data?.detail;
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  if (raw.code !== 'LIFECYCLE_CONFIRM_REJECTED' && !Array.isArray(raw.violations)) {
    return null;
  }
  return {
    code: raw.code || 'LIFECYCLE_CONFIRM_REJECTED',
    message: typeof raw.message === 'string' ? raw.message : null,
    violations: Array.isArray(raw.violations) ? raw.violations : [],
    lifecycle_semantics: raw.lifecycle_semantics,
    extraction_profile_id: raw.extraction_profile_id,
    contract_version: raw.contract_version,
    fieldErrors: mapLifecycleViolationsToFieldErrors(raw.violations),
  };
}
