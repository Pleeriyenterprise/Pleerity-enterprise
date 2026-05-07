import { getEvidenceStatus, workflowAwareMissingEvidenceLabel } from './evidenceStatus';

describe('workflowAwareMissingEvidenceLabel', () => {
  it('maps workflow classes to required copy', () => {
    expect(workflowAwareMissingEvidenceLabel({ workflow_class: 'DOCUMENT_UPLOAD' })).toBe(
      'Certificate or evidence document missing — action required',
    );
    expect(workflowAwareMissingEvidenceLabel({ workflow_class: 'GUIDED_DECLARATION' })).toBe(
      'Declaration not recorded — action required',
    );
    expect(workflowAwareMissingEvidenceLabel({ workflow_class: 'TENANT_DELIVERY' })).toBe(
      'Delivery record missing — action required',
    );
    expect(workflowAwareMissingEvidenceLabel({ workflow_class: 'REGISTRATION_TRACKING' })).toBe(
      'Registration details not recorded — action required',
    );
    expect(workflowAwareMissingEvidenceLabel({ workflow_class: 'EXTERNAL_ASSESSMENT_EVIDENCE' })).toBe(
      'Assessment not recorded — action required',
    );
    expect(workflowAwareMissingEvidenceLabel({ workflow_class: 'MULTI_EVIDENCE' })).toBe('Required evidence incomplete');
    expect(workflowAwareMissingEvidenceLabel({ workflow_class: 'GUIDANCE_ONLY' })).toBe('Guidance item — review recommended');
  });

  it('maps active standard rows to condition review copy', () => {
    expect(workflowAwareMissingEvidenceLabel({ workflow_class: 'ACTIVE_STANDARD' })).toBe('Condition status needs review');
    expect(workflowAwareMissingEvidenceLabel({ requirement_code: 'fitness_for_human_habitation' })).toBe(
      'Condition status needs review',
    );
  });

  it('uses tenancy-specific status copy when provided', () => {
    expect(
      workflowAwareMissingEvidenceLabel({
        requirement_code: 'tenancy_agreement',
        tenancy_agreement_status_text: 'Agreement not recorded — action required',
      }),
    ).toBe('Agreement not recorded — action required');
  });
});

describe('getEvidenceStatus', () => {
  it('uses multi-evidence chip text when workflow_class is MULTI_EVIDENCE', () => {
    const s = getEvidenceStatus('PENDING', { workflow_class: 'MULTI_EVIDENCE', evidence_doc_id: null });
    expect(s.text).toBe('Evidence incomplete');
    expect(s.subline).toBe('Required evidence incomplete');
  });

  it('uses assessment chip for EXTERNAL_ASSESSMENT_EVIDENCE', () => {
    const s = getEvidenceStatus('MISSING', { workflow_class: 'EXTERNAL_ASSESSMENT_EVIDENCE' });
    expect(s.text).toBe('Assessment incomplete');
  });

  it('uses workflow-aware subline for missing evidence states', () => {
    const s = getEvidenceStatus('PENDING', { workflow_class: 'GUIDED_DECLARATION', evidence_doc_id: null });
    expect(s.subline).toBe('Declaration not recorded — action required');
  });

  it('shows tenancy status subline for compliant tenancy rows', () => {
    const s = getEvidenceStatus('COMPLIANT', {
      requirement_code: 'tenancy_agreement',
      tenancy_agreement_status_text: 'Agreement recorded — unsigned',
    });
    expect(s.subline).toBe('Agreement recorded — unsigned');
  });
});

