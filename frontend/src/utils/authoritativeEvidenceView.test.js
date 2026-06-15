import {
  requirementAuthoritativeEvidenceIsRecordPrimary,
  requirementHasLinkedAuthoritativeDocument,
  resolveAuthoritativeEvidenceViewPath,
  shouldViewEvidenceInModalInspectPanel,
} from './authoritativeEvidenceView';

describe('authoritativeEvidenceView', () => {
  it('treats verified structured CER without document as record-primary', () => {
    const req = {
      property_id: 'p1',
      requirement_id: 'r1',
      evidence_authority: {
        state: 'VERIFIED_CURRENT',
        state_reason: 'verified_non_document_evidence',
        primary_evidence_record_id: 'cer_1',
      },
    };
    expect(requirementHasLinkedAuthoritativeDocument(req)).toBe(false);
    expect(requirementAuthoritativeEvidenceIsRecordPrimary(req)).toBe(true);
    expect(shouldViewEvidenceInModalInspectPanel(req)).toBe(true);
    expect(resolveAuthoritativeEvidenceViewPath(req)).toBe(
      '/properties/p1?tab=evidence&requirement_id=r1&open=intel&focus=submission',
    );
  });

  it('routes document-primary verified evidence to documents', () => {
    const req = {
      property_id: 'p1',
      requirement_id: 'r1',
      document_id: 'doc_1',
      evidence_authority: { effective_verified_document_id: 'doc_1' },
    };
    expect(requirementAuthoritativeEvidenceIsRecordPrimary(req)).toBe(false);
    expect(resolveAuthoritativeEvidenceViewPath(req)).toBe(
      '/documents?property_id=p1&requirement_id=r1',
    );
  });

  it('uses latest CER mode when present', () => {
    const req = { property_id: 'p1', requirement_id: 'r1' };
    const cer = { evidence_mode: 'INSPECTION_CHECKLIST' };
    expect(requirementAuthoritativeEvidenceIsRecordPrimary(req, cer)).toBe(true);
  });
});
