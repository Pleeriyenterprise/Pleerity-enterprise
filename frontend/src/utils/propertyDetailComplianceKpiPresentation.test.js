import {
  PROPERTY_DETAIL_COMPLIANCE_KPI_EXPLANATION,
  propertyDetailComplianceKpiCountsFromApi,
  propertyDetailComplianceKpiLabels,
} from './propertyDetailComplianceKpiPresentation';
import { REPORTING_SEMANTICS_LABELS } from './reportingSemanticsLabels';

describe('propertyDetailComplianceKpiPresentation', () => {
  it('reuses governed reporting semantics labels for Dashboard parity', () => {
    const labels = propertyDetailComplianceKpiLabels();
    expect(labels.requirementsSatisfied.label).toBe(
      REPORTING_SEMANTICS_LABELS.lifecycle_satisfied_count.label,
    );
    expect(labels.validForScoring.label).toBe(
      REPORTING_SEMANTICS_LABELS.compliant_requirement_count.label,
    );
    expect(labels.validForScoring.label).toBe('Valid for scoring');
    expect(labels.requirementsSatisfied.label).toBe('Requirements satisfied');
  });

  it('maps API KPI fields without frontend inference', () => {
    expect(
      propertyDetailComplianceKpiCountsFromApi({
        lifecycle_satisfied_count: 7,
        status_valid: 2,
        missing_evidence: 3,
      }),
    ).toEqual({ requirementsSatisfied: 7, validForScoring: 2, missingEvidence: 3 });
  });

  it('returns null when API fields absent', () => {
    expect(propertyDetailComplianceKpiCountsFromApi({})).toEqual({
      requirementsSatisfied: null,
      validForScoring: null,
      missingEvidence: null,
    });
    expect(propertyDetailComplianceKpiCountsFromApi(null)).toEqual({
      requirementsSatisfied: null,
      validForScoring: null,
      missingEvidence: null,
    });
  });

  it('explains both measures without implying hierarchy', () => {
    expect(PROPERTY_DETAIL_COMPLIANCE_KPI_EXPLANATION).toMatch(/Requirements satisfied/i);
    expect(PROPERTY_DETAIL_COMPLIANCE_KPI_EXPLANATION).toMatch(/Valid for scoring/i);
    expect(PROPERTY_DETAIL_COMPLIANCE_KPI_EXPLANATION).toMatch(/may legitimately differ/i);
  });
});
