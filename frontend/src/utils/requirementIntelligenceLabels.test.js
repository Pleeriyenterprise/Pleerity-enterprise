/**
 * @jest-environment jsdom
 */
import {
  humanApplicabilityClientLabel,
  formatAcceptedEvidenceModesForClient,
  activeComplianceJobClientSummary,
  requirementStatusSummaryForModal,
  humanWorkflowStatusLabel,
  humanComplianceStateLabel,
} from './requirementIntelligenceLabels';

describe('requirementIntelligenceLabels', () => {
  it('maps UNKNOWN applicability to plain language without UNKNOWN token', () => {
    const s = humanApplicabilityClientLabel('UNKNOWN');
    expect(s).not.toMatch(/UNKNOWN/i);
    expect(s.length).toBeGreaterThan(20);
  });

  it('formats allowed_evidence_modes from registry policy', () => {
    const lines = formatAcceptedEvidenceModesForClient({
      registry_metadata: {
        evidence_resolution: {
          allowed_evidence_modes: ['DOCUMENT_UPLOAD', 'STRUCTURED_DECLARATION'],
        },
      },
    });
    expect(lines).toEqual(['Document upload', 'Structured declaration']);
  });

  it('summarises active job without raw id in copy', () => {
    const s = activeComplianceJobClientSummary({
      job_id: '7599d2bb-cafe',
      status: 'IN_PROGRESS',
      contractor_name: 'ABC Electrical',
      next_visit_at: '2026-05-12T10:00:00.000Z',
    });
    expect(s.navigateJobId).toBe('7599d2bb-cafe');
    expect(s.lines.join(' ')).not.toContain('7599d2bb');
    expect(s.lines.some((l) => /ABC Electrical/.test(l))).toBe(true);
  });

  it('dedupes duplicate missing-evidence lines between compliance and evidence', () => {
    const r = {
      workflow_status: 'ACTION_REQUIRED',
      compliance_state: 'MISSING',
      evidence_state: 'MISSING',
    };
    const sum = requirementStatusSummaryForModal(r);
    expect(sum.evidenceLine).toBeNull();
    expect(sum.compliance).toMatch(/missing required evidence/i);
  });

  it('uses workflow-aware missing-evidence wording for guided declaration', () => {
    const sum = requirementStatusSummaryForModal({
      workflow_class: 'GUIDED_DECLARATION',
      compliance_state: 'MISSING',
      status: 'MISSING',
    });
    expect(sum.evidenceLine).toBe('Declaration not recorded — action required');
  });

  it('uses workflow-aware missing-evidence wording for external assessment', () => {
    const sum = requirementStatusSummaryForModal({
      workflow_class: 'EXTERNAL_ASSESSMENT_EVIDENCE',
      compliance_state: 'MISSING',
      status: 'MISSING',
    });
    expect(sum.evidenceLine).toBe('Assessment not recorded — action required');
  });

  it('uses human-friendly workflow and compliance defaults', () => {
    expect(humanWorkflowStatusLabel('ACTION_REQUIRED')).toBe('Action needed');
    expect(humanComplianceStateLabel('PENDING_VERIFICATION')).toBe('Evidence submitted and awaiting review');
    expect(humanComplianceStateLabel('MISSING')).toBe('Missing required evidence');
  });
});
