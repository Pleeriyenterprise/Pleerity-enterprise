import {
  buildComplianceEvidenceRecordDisplay,
  formatFieldValueForDisplay,
} from './complianceEvidenceSubmissionView';

describe('complianceEvidenceSubmissionView display hygiene', () => {
  it('never JSON-stringifies empty answer objects', () => {
    expect(formatFieldValueForDisplay({ answer: null, notes: null, observation: null })).toBe('Not provided');
    expect(formatFieldValueForDisplay(null)).toBe('Not provided');
  });

  it('omits empty optional structured fields from display', () => {
    const { sections } = buildComplianceEvidenceRecordDisplay({
      evidence_mode: 'STRUCTURED_DECLARATION',
      evidence_payload: {
        declaration_statement: 'Tenancy on file',
        structured_fields: {
          tenant_name: { answer: 'Alex' },
          optional_note: { answer: null, notes: null },
        },
      },
    });
    const rows = sections[0]?.rows || [];
    const labels = rows.map((r) => r.label);
    expect(labels).toContain('Tenant Name');
    expect(labels).not.toContain('Optional Note');
    expect(rows.find((r) => r.label === 'Tenant Name')?.value).toBe('Alex');
  });
});
