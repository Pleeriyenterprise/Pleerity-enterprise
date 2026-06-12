import { normalizeOperationalPrimaryKey } from './primaryActionResolver';

export const CONTRACTOR_NETWORK_FEATURE_KEY = 'contractor_network';

export const CONTRACTOR_NETWORK_LOCKED_TITLE = 'Contractor assignment is a Professional feature';

export const CONTRACTOR_NETWORK_LOCKED_BODY =
  'Assigning contractors from your jobs and issues is included on the Professional plan. Upgrade to use the contractor network, or contact support if you need help with the next step.';

/** @param {{ key?: string }|null|undefined} primary */
export function isIssueAssignContractorLocked(primary, hasContractorNetwork) {
  if (!primary || hasContractorNetwork) return false;
  return normalizeOperationalPrimaryKey(primary.key) === 'assign_contractor';
}
