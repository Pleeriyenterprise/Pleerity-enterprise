import {
  getMatchOutcomePresentation,
  getCanonicalDocumentTypeLabel,
  getMismatchReasonPresentation,
  getConfidencePresentation,
  getValidationSnapshotPresentation,
  getAnomalyRiskPresentation,
  getExtractionStatusPresentation,
  hasMatchEvaluationAttempted,
  getPendingDocumentOperationalPresentation,
  buildTechnicalDetailsRows,
} from './adminOperationalPresentation';

describe('adminOperationalPresentation', () => {
  it('maps match outcomes to operational labels', () => {
    expect(getMatchOutcomePresentation('MATCH_LIKELY').label).toBe('Likely match found');
    expect(getMatchOutcomePresentation('NEEDS_ADMIN_REVIEW').label).toBe('Possible match needs review');
    expect(getMatchOutcomePresentation('MATCH_CONFIRMED').label).toBe('Match confirmed');
  });

  it('degrades unknown enums without exposing raw tokens in label', () => {
    const p = getMatchOutcomePresentation('UNKNOWN_NEW_ENUM');
    expect(p.label).toBe('Unknown New Enum');
    expect(p.label).not.toBe('UNKNOWN_NEW_ENUM');
    expect(p.canonicalValue).toBe('UNKNOWN_NEW_ENUM');
  });

  it('maps canonical document types', () => {
    expect(getCanonicalDocumentTypeLabel('RIGHT_TO_RENT_EVIDENCE')).toBe('Right to Rent evidence');
    expect(getCanonicalDocumentTypeLabel('GAS_SAFETY')).toBe('Gas safety certificate');
  });

  it('maps mismatch reason codes', () => {
    expect(getMismatchReasonPresentation('NO_REQUIREMENT_LINK').label).toBe(
      'No matching requirement linked yet'
    );
  });

  it('presents confidence as percent with tier', () => {
    const p = getConfidencePresentation(0.57);
    expect(p.label).toBe('57% confidence');
    expect(p.tier).toBe('low');
    expect(p.tierLabel).toBe('Low confidence');
  });

  it('presents high and medium confidence tiers', () => {
    expect(getConfidencePresentation(0.92).tierLabel).toBe('High confidence');
    expect(getConfidencePresentation(0.75).tierLabel).toBe('Medium confidence');
  });

  it('humanizes validation snapshot status', () => {
    const p = getValidationSnapshotPresentation({
      validation_status: 'WARN',
      warnings: ['MISSING_EXPIRY_DATE'],
      failures: [],
    });
    expect(p.label).toContain('Warnings found');
    expect(p.label).not.toMatch(/^WARN\b/);
  });

  it('humanizes anomaly risk', () => {
    expect(getAnomalyRiskPresentation(0.71).label).toBe('High-risk anomaly detected');
    expect(getAnomalyRiskPresentation(0.71).label).not.toContain('0.71');
  });

  it('humanizes extraction queue status', () => {
    expect(getExtractionStatusPresentation('NEEDS_REVIEW').label).toBe('Extraction needs review');
    expect(getExtractionStatusPresentation('FAILED').label).toBe('Extraction failed');
  });

  it('detects match evaluation attempted', () => {
    expect(hasMatchEvaluationAttempted({ match_outcome: 'MATCH_LIKELY' })).toBe(true);
    expect(hasMatchEvaluationAttempted({})).toBe(false);
  });

  it('shows processing state when match not attempted', () => {
    const op = getPendingDocumentOperationalPresentation({ document_id: 'd1', status: 'UPLOADED' });
    expect(op.suggestedMatch.label).toBe('Matching requirement…');
    expect(op.reviewStatus.label).toBe('Review preparation in progress');
  });

  it('buildTechnicalDetailsRows preserves canonical values', () => {
    const rows = buildTechnicalDetailsRows({
      document_id: 'doc-1',
      match_outcome: 'MATCH_LIKELY',
      predicted_document_type: 'RIGHT_TO_RENT_EVIDENCE',
    });
    expect(rows.some((r) => r.key === 'match_outcome' && r.value === 'MATCH_LIKELY')).toBe(true);
  });

});
