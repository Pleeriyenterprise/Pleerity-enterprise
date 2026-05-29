/**
 * Client-facing copy for jurisdiction / compliance profiling.
 * Keep wording non-prescriptive (product tracking, not legal advice).
 */

export const JURISDICTION_OPTIONS = ['Scotland', 'England', 'Wales', 'Northern Ireland'];

/** API `jurisdiction_source` — how the effective jurisdiction is chosen for this property. */
export const JURISDICTION_SOURCE_LABEL = {
  property_record: 'Property',
  account_default: 'Account default',
  /** No valid jurisdiction on property or account — scoring uses system default until resolved. */
  system_default: 'Required / System default',
};

export function jurisdictionSourceLabel(source) {
  if (!source) return '—';
  return JURISDICTION_SOURCE_LABEL[source] || source;
}

/** Backend scoring buckets (compliance_scoring_v2.normalize_jurisdiction). */
export function scoringProfileForDefaultLabel(defaultJurisdiction) {
  const j = (defaultJurisdiction || '').trim();
  if (j === 'Scotland') return 'SCOTLAND';
  return 'ENGLAND_WALES';
}

/** Shown when property + client both lack a recognised jurisdiction — scoring uses system default (England / EW bucket). */
export const JURISDICTION_FALLBACK_ALERT_TITLE = 'Default jurisdiction in use';

export const JURISDICTION_FALLBACK_ALERT_BODY =
  'At least one context is using the system default (England & Wales–style rules) because no jurisdiction is set on the property record and no account default is saved. Your score and dates may not match the right region until you set jurisdiction.';

export const JURISDICTION_FALLBACK_ALERT_BODY_PROPERTY =
  'This property is scored using the system default (England & Wales–style rules) because neither the property record nor your account has a recognised jurisdiction saved. Set your account default in settings, or set jurisdiction on this property.';

/** Property page when compliance_basis is client_default (account default applies; property record has no explicit jurisdiction). */
export const JURISDICTION_ACCOUNT_DEFAULT_NOTICE_TITLE = 'Using your account default jurisdiction';

export function jurisdictionAccountDefaultNoticeBody(effectiveLabel) {
  const label = (effectiveLabel || '').trim();
  const where = label ? ` (${label})` : '';
  return (
    `This property is using your account default jurisdiction${where} because no region is set on the property record yet. ` +
    'Choose the correct region in “Jurisdiction on this property” below and save — you can complete this on this page. ' +
    'After you save, scoring and requirements will use that property-level jurisdiction.'
  );
}

/** Checklist step “Review jurisdiction settings” deep-links to account settings; saving does not bulk-update existing properties. */
export const JURISDICTION_CHECKLIST_SET_JURISDICTIONS_NOTE =
  'Saving your default in Jurisdiction settings updates your account only — it does not write onto existing property records. ' +
  'New properties may use that default until you set them on each property. ' +
  'To backfill many empty records at once, save your default then use “Apply default to missing properties only” on the same settings page (it never overwrites a jurisdiction already on a property). ' +
  'You can still set a different jurisdiction on any property when you need an override.';

export const JURISDICTION_FALLBACK_CTA = 'Set jurisdiction';

/** Onboarding blocking dialog — make consequences clear; not legal advice. */
export const JURISDICTION_ONBOARDING_GATE_TITLE = 'Set jurisdiction on each property record';

export const JURISDICTION_ONBOARDING_GATE_LEAD =
  'One or more properties have no jurisdiction saved on the property record. Your account default can be used for scoring until then, but you should still review and set the correct jurisdiction on each property for accuracy. ' +
  'Where no valid default exists, the product may use a system default (England & Wales–style rules).';

export const JURISDICTION_ONBOARDING_GATE_CONSEQUENCE =
  'Your portfolio score, requirement lists, due dates, and risk signals for those properties may not reflect the correct region. That is an accuracy risk — not a legal ruling — but it can mis-prioritise work and mis-state standing if the wrong profile is applied.';

export const JURISDICTION_ONBOARDING_GATE_CTA_HINT =
  'Prefer setting each property now; only use acknowledgement if you intentionally accept that risk for the moment.';

export const JURISDICTION_FALLBACK_ACK_CHECKBOX_LABEL =
  'I understand that without a jurisdiction on each affected property record, scores and requirements shown for those properties may be incorrect, and I accept continuing with account or system assumptions until I update each property.';

export const JURISDICTION_FALLBACK_ACK_SUBMIT_LABEL = 'Record acknowledgement and continue';

export const JURISDICTION_FALLBACK_ACK_VALIDATION_ERROR =
  'Confirm the checkbox to record that you understand the consequences before continuing.';

/** Portfolio-level (dashboard / Today) after client acknowledgement — one quiet line; property detail keeps the stronger alert. */
export const JURISDICTION_PORTFOLIO_REMINDER_COMPACT =
  'Reminder: some properties still have no jurisdiction on record — scores and rules may not match each property until you set them.';

export const JURISDICTION_IMPACT_INTRO =
  'This determines the legal compliance rules applied to your properties in Compliance Vault Pro — which requirements apply, how they appear in your score, and how they are surfaced in dashboards and risk signals.';

export const JURISDICTION_SCOPE_GLOBAL =
  'Your default applies to every property that does not have its own jurisdiction set on the property record. New properties start with this default until you change it for that property.';

export const JURISDICTION_SCOPE_PER_PROPERTY =
  'You can override jurisdiction on individual property records; those overrides take precedence for scoring.';

export const JURISDICTION_NI_NOTE =
  'Northern Ireland is supported for your portfolio settings; scoring currently uses the England & Wales profile in the product for Northern Ireland, England, and Wales, and a separate profile for Scotland.';

export function impactRuleExamplesForProfile(profileKey) {
  if (profileKey === 'SCOTLAND') {
    return [
      'Gas safety records (where gas is present)',
      'Electrical installation condition (EICR-style tracking)',
      'Energy performance (EPC)',
      'Fire detection and alarm coverage',
      'Legionella where water systems apply',
    ];
  }
  return [
    'Gas safety records (where gas is present)',
    'Electrical installation condition (EICR-style tracking)',
    'Building energy performance (EPC)',
    'Fire detection and alarm coverage',
    'Legionella where water systems apply',
  ];
}
