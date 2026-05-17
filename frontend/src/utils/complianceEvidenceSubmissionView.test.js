import {
  buildComplianceEvidenceRecordDisplay,
  isViewExistingSubmissionCta,
  pickLatestComplianceEvidenceRecord,
  summarizeSubmittedEvidenceRecord,
} from './complianceEvidenceSubmissionView';

describe('complianceEvidenceSubmissionView', () => {
  it('picks latest non-archived record', () => {
    const records = [
      { evidence_record_id: 'a', archived: true },
      { evidence_record_id: 'b', evidence_mode: 'STRUCTURED_DECLARATION' },
    ];
    expect(pickLatestComplianceEvidenceRecord(records)?.evidence_record_id).toBe('b');
  });

  it('builds structured declaration display from persisted payload', () => {
    const display = buildComplianceEvidenceRecordDisplay({
      evidence_mode: 'STRUCTURED_DECLARATION',
      created_at: '2026-05-01T12:00:00Z',
      verification_status: 'PENDING',
      evidence_payload: {
        declaration_statement: 'I confirm alarms are fitted.',
        structured_fields: { alarm_count: '3' },
      },
    });
    expect(display.sections[0].rows.some((r) => r.value.includes('alarms'))).toBe(true);
    expect(display.meta.some((m) => m.label === 'Submitted at')).toBe(true);
  });

  it('detects view-submission CTAs', () => {
    expect(
      isViewExistingSubmissionCta({
        primary_action_handler: 'guided_evidence',
        primary_action_label: 'View submission',
      }),
    ).toBe(true);
    expect(
      isViewExistingSubmissionCta({
        primary_action_handler: 'guided_evidence',
        primary_action_label: 'Record declaration',
      }),
    ).toBe(false);
  });

  it('summarizes authoritative evidence_record for post-submit', () => {
    const lines = summarizeSubmittedEvidenceRecord({
      evidence_mode: 'STRUCTURED_DECLARATION',
      created_at: '2026-05-01',
      verification_status: 'PENDING',
      evidence_payload: { declaration_statement: 'Saved line', structured_fields: {} },
    });
    expect(lines.some((l) => l.includes('Saved line') || l.includes('Structured'))).toBe(true);
  });
});
