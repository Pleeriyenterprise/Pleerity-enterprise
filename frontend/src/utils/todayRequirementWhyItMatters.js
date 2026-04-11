/**
 * Today task cards — one-line “why it matters” from requirement metadata (UI only).
 * Keys match `normalizeRequirementCode` output (presentDomain).
 */

import { normalizeRequirementCode } from '../domain/presentDomain';

/** Canonical requirement_code → single sentence (max one each). */
export const TODAY_REQUIREMENT_WHY_IT_MATTERS_BY_CODE = {
  gas_safety:
    'Gas safety certification is legally required for occupied property and tenant safety.',
  fire_alarm:
    'Fire alarm inspection is required to maintain fire safety compliance.',
  legionella:
    'A current legionella assessment helps protect tenant health and reduce enforcement risk.',
  eicr:
    'Electrical safety records are required to show the installation is safe for continued use.',
  pat:
    'Portable appliance testing helps show electrical equipment is safe and up to date.',
  smoke_alarms:
    'Working smoke alarms are required so occupants get early warning in a fire.',
  co_alarms:
    'Carbon monoxide alarms are required where applicable so tenants are protected from CO risk.',
  epc:
    'An up-to-date EPC is required when letting and keeps this property’s energy record lawful.',
  fire_risk_assessment:
    'A fire risk assessment is required to identify and manage fire safety for this building.',
  hmo_license:
    'An HMO licence is required when licensing thresholds apply—without it you risk enforcement.',
  deposit_pi:
    'Protected deposits are required by law so tenant money is safeguarded correctly.',
  right_to_rent:
    'Right to rent checks are required before occupation to meet immigration housing rules.',
  how_to_rent:
    'Providing the current How to rent guide is required so tenants receive prescribed information.',
  tenancy_agreement:
    'A compliant tenancy agreement records terms clearly and supports dispute and deposit rules.',
  oil_tank:
    'Oil storage compliance reduces environmental and fire risk and supports insurance expectations.',
  boiler_service:
    'Boiler servicing supports safe operation and valid warranty or insurance for heating systems.',
};

/** Map variant normalised codes to a canonical key in TODAY_REQUIREMENT_WHY_IT_MATTERS_BY_CODE. */
const WHY_IT_MATTERS_CODE_ALIASES = {
  gas_safety_certificate: 'gas_safety',
  cp12: 'gas_safety',
  fire_detection: 'fire_alarm',
  portable_appliance_test: 'pat',
  electrical_safety: 'eicr',
  electrical_installation_condition_report: 'eicr',
  legionella_risk_assessment: 'legionella',
  deposit_protection: 'deposit_pi',
};

export const TODAY_REQUIREMENT_WHY_IT_MATTERS_FALLBACK =
  'This requirement is needed to keep this property compliant.';

/**
 * @param {Record<string, unknown>|null|undefined} task
 * @returns {string}
 */
export function todayRequirementWhyItMattersLine(task) {
  if (!task || typeof task !== 'object') return TODAY_REQUIREMENT_WHY_IT_MATTERS_FALLBACK;
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const raw = meta.requirement_code || meta.requirement_type || meta.code || '';
  let key = normalizeRequirementCode(raw);
  if (!key) return TODAY_REQUIREMENT_WHY_IT_MATTERS_FALLBACK;
  const canonical = WHY_IT_MATTERS_CODE_ALIASES[key] || key;
  const line = TODAY_REQUIREMENT_WHY_IT_MATTERS_BY_CODE[canonical];
  if (line) return line;
  return TODAY_REQUIREMENT_WHY_IT_MATTERS_FALLBACK;
}
