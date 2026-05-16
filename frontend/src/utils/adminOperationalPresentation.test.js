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
  getEnrichmentReadinessPresentation,
  buildTechnicalDetailsRows,
  ENRICHMENT_READINESS,
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

  it('uses API enrichment readiness labels', () => {
    const p = getEnrichmentReadinessPresentation({
      enrichment_readiness: 'PROCESSING',
      enrichment_readiness_label: 'Extraction in progress',
    });
    expect(p.label).toBe('Extraction in progress');
    expect(p.canonicalValue).toBe('PROCESSING');
  });

  it('renders failed extraction distinctly from processing', () => {
    const op = getPendingDocumentOperationalPresentation({
      enrichment_readiness: ENRICHMENT_READINESS.FAILED,
      enrichment_readiness_label: 'Extraction failed — review manually',
      extraction_status: 'FAILED',
    });
    expect(op.readiness.tone).toBe('danger');
    expect(op.suggestedMatch.label).toContain('failed');
    expect(op.reviewStatus.label).toContain('failed');
  });

  it('shows confidence unavailable while not ready', () => {
    const op = getPendingDocumentOperationalPresentation({
      enrichment_readiness: 'PROCESSING',
      match_confidence: 0.9,
    });
    expect(op.confidence.label).toBe('Confidence unavailable');
  });

  it('includes readiness fields in technical details', () => {
    const rows = buildTechnicalDetailsRows({
      enrichment_readiness: 'READY',
      match_status: 'COMPLETE',
      enrichment_latency_ms: 1200,
    });
    expect(rows.some((r) => r.key === 'enrichment_readiness' && r.value === 'READY')).toBe(true);
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
