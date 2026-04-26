import {
  humanWorkflowStatusLabel,
  humanComplianceStateLabel,
  humanEvidenceStateLabel,
  requirementWorkflowDisplayPair,
} from './requirementIntelligenceLabels';

describe('requirementIntelligenceLabels', () => {
  it('maps workflow and compliance tokens to user-facing labels', () => {
    expect(humanWorkflowStatusLabel('ACTION_REQUIRED')).toBe('Action required');
    expect(humanComplianceStateLabel('MISSING')).toBe('Evidence missing');
    expect(humanWorkflowStatusLabel('OVERDUE')).toBe('Overdue');
    expect(humanComplianceStateLabel('VALID')).toBe('Verified and current');
  });

  it('maps evidence state VERIFIED_CURRENT', () => {
    expect(humanEvidenceStateLabel('VERIFIED_CURRENT')).toBe('Verified and current');
  });

  it('prefers API-provided labels when present on the requirement object', () => {
    const pair = requirementWorkflowDisplayPair({
      workflow_status: 'ACTION_REQUIRED',
      compliance_state: 'MISSING',
      workflow_status_label: 'Custom workflow',
      compliance_state_label: 'Custom compliance',
    });
    expect(pair.workflow).toBe('Custom workflow');
    expect(pair.compliance).toBe('Custom compliance');
  });
});
