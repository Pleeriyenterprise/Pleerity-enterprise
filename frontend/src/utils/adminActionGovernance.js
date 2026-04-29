import policyRegistry from '../config/adminActionPolicyRegistry.json';

const RISK_BADGE_CLASS = {
  privacy_sensitive: 'border-violet-200 bg-violet-50 text-violet-800',
  high_impact_operational: 'border-amber-200 bg-amber-50 text-amber-800',
  dangerous_global: 'border-rose-200 bg-rose-50 text-rose-800',
};

const ESCALATION_TEXT = {
  privacy_sensitive: 'Owner oversight recommended. Escalate if target identity is unclear.',
  high_impact_operational: 'Escalate to engineering if one controlled retry does not restore consistency.',
  dangerous_global: 'Global-impact operation. Owner approval and post-run verification required.',
};

export const getAdminActionPolicy = (actionId) => policyRegistry?.[actionId] || null;

export const getGovernanceRiskBadgeClass = (actionId) => {
  const policy = getAdminActionPolicy(actionId);
  return RISK_BADGE_CLASS[policy?.risk_class] || 'border-slate-200 bg-slate-50 text-slate-700';
};

export const getGovernanceWarning = (actionId) => {
  const policy = getAdminActionPolicy(actionId);
  if (!policy) return 'Governance policy missing for this action.';
  const parts = [`Risk: ${policy.risk_class.replace(/_/g, ' ')}`, `Operator: ${policy.operator_level.replace(/_/g, ' ')}`];
  if (policy.affects_multiple_customers) parts.push('Affects multiple customers');
  if (policy.irreversible) parts.push('Irreversible');
  return parts.join(' - ');
};

export const getGovernanceEscalationGuidance = (actionId) => {
  const policy = getAdminActionPolicy(actionId);
  if (!policy) return 'Escalate to engineering for manual verification before running this action.';
  return ESCALATION_TEXT[policy.risk_class] || ESCALATION_TEXT.high_impact_operational;
};

export const getGovernanceConfirmationWording = (actionId) => {
  const policy = getAdminActionPolicy(actionId);
  if (!policy || !policy.requires_confirmation) return 'Confirm action';
  return `I confirm I reviewed impact and reason for ${policy.action_id.replace(/_/g, ' ')}.`;
};

