import { isConditionStandardWorkflowHint, isMultiEvidenceStyleWorkflow, isConditionStandardActiveStandardRow, normalizeWorkflowClass } from './workflowSemantics';

describe('workflowSemantics', () => {
  it('normalizes workflow class', () => {
    expect(normalizeWorkflowClass(' multi_evidence ')).toBe('MULTI_EVIDENCE');
  });

  it('treats MULTI_EVIDENCE and legacy GUIDED_EVIDENCE_RESOLUTION as multi-style', () => {
    expect(isMultiEvidenceStyleWorkflow('MULTI_EVIDENCE')).toBe(true);
    expect(isMultiEvidenceStyleWorkflow('GUIDED_EVIDENCE_RESOLUTION')).toBe(true);
    expect(isMultiEvidenceStyleWorkflow('DOCUMENT_UPLOAD')).toBe(false);
  });

  it('detects condition standard rows by code or ACTIVE_STANDARD', () => {
    expect(isConditionStandardWorkflowHint('', { requirement_code: 'fitness_for_human_habitation' })).toBe(true);
    expect(isConditionStandardWorkflowHint('GUIDANCE_ONLY', { requirement_code: 'repairing_standard' })).toBe(true);
    expect(isConditionStandardWorkflowHint('ACTIVE_STANDARD', {})).toBe(true);
    expect(isConditionStandardWorkflowHint('DOCUMENT_UPLOAD', { requirement_code: 'gas_safety' })).toBe(false);
  });

  it('detects CONDITION_STANDARD_ACTIVE_STANDARD enriched rows', () => {
    expect(
      isConditionStandardActiveStandardRow({
        workflow_family: 'CONDITION_STANDARD_ACTIVE_STANDARD',
        ops_verification_family: 'CONDITION_STANDARD_ACTIVE_STANDARD',
        requirement_code: 'repairing_standard',
      }),
    ).toBe(true);
    expect(isConditionStandardActiveStandardRow({ requirement_code: 'gas_safety' })).toBe(false);
  });
});
