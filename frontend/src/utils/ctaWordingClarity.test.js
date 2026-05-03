/**
 * @jest-environment jsdom
 */
import { sanitizeCommandCenterCtaLabel } from './clientCommandCenter';
import { mergeComplianceCreateIfEligible } from './todayWorkflowPolicy';
import { resolveRiskSignalPrimaryKey, OUTCOME_PRIMARY } from './primaryActionResolver';

describe('primaryActionResolver risk / maintenance CTA labels', () => {
  it('does not use vague Fix issue / Review issue strings', () => {
    const sig = (suggested) => ({ suggested_actions: suggested, risk_type: 'test' });
    expect(resolveRiskSignalPrimaryKey(sig(['schedule_inspection']), true, true)).toEqual({
      key: 'compliance_inspection',
      label: OUTCOME_PRIMARY.startInspectionJob,
    });
    expect(resolveRiskSignalPrimaryKey(sig(['schedule_inspection']), true, false)).toEqual({
      key: 'log_inspection_issue',
      label: OUTCOME_PRIMARY.logInspectionIssue,
    });
    expect(resolveRiskSignalPrimaryKey(sig(['create_work_order']), true, true)).toEqual({
      key: 'maintenance_job',
      label: OUTCOME_PRIMARY.startMaintenanceJob,
    });
    expect(resolveRiskSignalPrimaryKey(sig(['create_issue']), true, true)).toEqual({
      key: 'maintenance_issue',
      label: OUTCOME_PRIMARY.logMaintenanceIssue,
    });
    expect(resolveRiskSignalPrimaryKey(sig([]), true, true)).toEqual({
      key: 'review',
      label: OUTCOME_PRIMARY.reviewRiskSignal,
    });
  });
});

describe('sanitizeCommandCenterCtaLabel', () => {
  it('prefers server take_action.primary.label when present', () => {
    const task = {
      source_type: 'requirement',
      primary_action_label: 'Ignored when take_action wins',
      metadata: {
        take_action: {
          primary: { label: 'Resolver-provided label from API' },
        },
      },
    };
    expect(sanitizeCommandCenterCtaLabel('Upload evidence', task)).toBe('Resolver-provided label from API');
  });

  it('maps review risk signal to Review risk signal, not Review issue', () => {
    const task = { source_type: 'risk_signal', metadata: {} };
    expect(sanitizeCommandCenterCtaLabel('Review risk signal', task)).toBe('Review risk signal');
  });

  it('falls back to Review risk signal for risk_signal rows without mapped primary string', () => {
    const task = { source_type: 'risk_signal', metadata: { action_type: 'risk_signal' }, primary_action_label: '' };
    expect(sanitizeCommandCenterCtaLabel('', task)).toBe('Review risk signal');
  });

  it('uses Review maintenance issue for maintenance issue rows', () => {
    const task = { source_type: 'issue', metadata: {} };
    expect(sanitizeCommandCenterCtaLabel('', task)).toBe('Review maintenance issue');
  });
});

describe('mergeComplianceCreateIfEligible', () => {
  it('uses Create compliance job for synthetic compliance WO action label', () => {
    const task = {
      metadata: {
        compliance_execution_booking: {
          eligible: true,
          linked_property_requirement_id: 'req-1',
          property_id: 'p1',
        },
      },
    };
    const out = mergeComplianceCreateIfEligible(task, 'compliance', [], true);
    expect(out[0].id).toBe('create_compliance_work_order');
    expect(out[0].label).toBe('Create compliance job');
  });
});
