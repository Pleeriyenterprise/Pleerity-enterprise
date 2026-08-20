/**
 * PROPERTY-DETAIL-PRESENTATION-AUTHORITY-ALIGNMENT-01
 * Property Detail KPI labels and copy — presentation only; no count authority.
 * Labels reuse reportingSemanticsLabels (Dashboard / score reporting alignment).
 */

import { REPORTING_SEMANTICS_LABELS } from './reportingSemanticsLabels';

/** API field on compliance-detail.kpis for lifecycle satisfaction count. */
export const PROPERTY_DETAIL_KPI_FIELD_LIFECYCLE_SATISFIED = 'lifecycle_satisfied_count';

/** API field on compliance-detail.kpis for score-valid count (COMPLIANT|VALID). */
export const PROPERTY_DETAIL_KPI_FIELD_STATUS_VALID = 'status_valid';

/**
 * Governed Property Detail KPI presentation (labels + tooltips).
 * @returns {{ requirementsSatisfied: { label: string, tooltip: string }, validForScoring: { label: string, tooltip: string } }}
 */
export function propertyDetailComplianceKpiLabels() {
  return {
    requirementsSatisfied: REPORTING_SEMANTICS_LABELS.lifecycle_satisfied_count,
    validForScoring: REPORTING_SEMANTICS_LABELS.compliant_requirement_count,
  };
}

/** Card-level explanation — both measures, no hierarchy implied. */
export const PROPERTY_DETAIL_COMPLIANCE_KPI_EXPLANATION =
  'Requirements satisfied counts obligations currently met through evidence, declarations, or accepted compliance records. Valid for scoring counts obligations currently contributing to compliance scoring. These measures use different authorities and may legitimately differ.';

/** API field on compliance-detail.kpis for Dashboard-aligned missing evidence. */
export const PROPERTY_DETAIL_KPI_FIELD_MISSING_EVIDENCE = 'missing_evidence';

/**
 * Map compliance-detail KPI payload to presentation fields (API authority only).
 * @param {Record<string, unknown>|null|undefined} kpis
 * @returns {{ requirementsSatisfied: number|null, validForScoring: number|null, missingEvidence: number|null }}
 */
export function propertyDetailComplianceKpiCountsFromApi(kpis) {
  if (!kpis || typeof kpis !== 'object') {
    return { requirementsSatisfied: null, validForScoring: null, missingEvidence: null };
  }
  const lifecycle = kpis[PROPERTY_DETAIL_KPI_FIELD_LIFECYCLE_SATISFIED];
  const statusValid = kpis[PROPERTY_DETAIL_KPI_FIELD_STATUS_VALID];
  const missingEvidence = kpis[PROPERTY_DETAIL_KPI_FIELD_MISSING_EVIDENCE];
  return {
    requirementsSatisfied:
      lifecycle != null && lifecycle !== '' && !Number.isNaN(Number(lifecycle))
        ? Number(lifecycle)
        : null,
    validForScoring:
      statusValid != null && statusValid !== '' && !Number.isNaN(Number(statusValid))
        ? Number(statusValid)
        : null,
    missingEvidence:
      missingEvidence != null && missingEvidence !== '' && !Number.isNaN(Number(missingEvidence))
        ? Number(missingEvidence)
        : null,
  };
}
