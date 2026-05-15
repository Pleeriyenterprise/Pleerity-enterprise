import {
  getAdminActionPolicy,
  getGovernanceConfirmationWording,
  getGovernanceEscalationGuidance,
  getGovernanceRiskBadgeClass,
  getGovernanceWarning,
} from './adminActionGovernance';

const COVERED_ACTIONS = [
  'start_impersonation',
  'run_subscription_lifecycle_batch',
  'run_stripe_reconcile_batch',
  'change_plan',
  'force_provision',
  'reconcile_subscription_payment_ledger',
  'unlock_account',
  'retry_agreement_issuance',
  'backfill_evidence_match_batch',
];

describe('adminActionGovernance', () => {
  it('loads phase 1 policy metadata for all 9 covered actions', () => {
    const fields = [
      'action_id',
      'risk_class',
      'operator_level',
      'requires_reason',
      'requires_confirmation',
      'requires_step_up',
      'affects_multiple_customers',
      'irreversible',
    ];
    COVERED_ACTIONS.forEach((actionId) => {
      const policy = getAdminActionPolicy(actionId);
      expect(policy).toBeTruthy();
      fields.forEach((field) => expect(policy).toHaveProperty(field));
      expect(policy.action_id).toBe(actionId);
    });
  });

  it('renders shared badges/warnings/guidance/confirmation for all 9 actions', () => {
    COVERED_ACTIONS.forEach((actionId) => {
      expect(getGovernanceRiskBadgeClass(actionId)).toMatch(/border-/);
      expect(getGovernanceWarning(actionId)).toMatch(/Risk:/i);
      expect(getGovernanceEscalationGuidance(actionId).length).toBeGreaterThan(10);
      expect(getGovernanceConfirmationWording(actionId).length).toBeGreaterThan(10);
    });
  });
});
