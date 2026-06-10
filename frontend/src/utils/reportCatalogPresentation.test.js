import {
  REPORT_CATALOG,
  EXPORT_GRADE_TAXONOMY,
  assertClientReportCopySafe,
  enrichReportFromApi,
  sortReportsForCatalog,
  canonicalReportFilename,
  isSpecialtyReport,
} from './reportCatalogPresentation';
import { operationalLabelForToken } from './presentationLanguage';

describe('reportCatalogPresentation', () => {
  it('defines all five converged report classes', () => {
    expect(REPORT_CATALOG.audit_evidence_pack.canonicalName).toBe('Audit Evidence Pack');
    expect(REPORT_CATALOG.evidence_readiness.canonicalName).toBe('Evidence Readiness Report');
    expect(REPORT_CATALOG.monthly_digest.canonicalName).toBe('Monthly Operations Intelligence Digest');
    expect(REPORT_CATALOG.requirements.canonicalName).toBe('Requirements Report');
    expect(REPORT_CATALOG.compliance_summary.canonicalName).toBe('Compliance Summary Report');
  });

  it('assigns export-grade taxonomy without backend enum leakage', () => {
    Object.values(REPORT_CATALOG).forEach((entry) => {
      expect(entry.exportGrade).toBeTruthy();
      expect(assertClientReportCopySafe(entry.purpose)).toBe(true);
      expect(assertClientReportCopySafe(entry.audience)).toBe(true);
      expect(entry.purpose.toLowerCase()).not.toContain('triage at a glance');
      expect(entry.purpose).not.toMatch(/UNKNOWN_DATE|workflow_class/i);
    });
    expect(REPORT_CATALOG.audit_evidence_pack.exportGrade).toBe(EXPORT_GRADE_TAXONOMY.EVIDENTIARY_ARCHIVE);
    expect(REPORT_CATALOG.compliance_summary.exportGrade).toBe(EXPORT_GRADE_TAXONOMY.EXECUTIVE_OVERVIEW);
  });

  it('enriches API catalog rows with canonical presentation', () => {
    const enriched = enrichReportFromApi({
      id: 'compliance_summary',
      name: 'Legacy name',
      description: 'Legacy description',
      formats: ['csv', 'pdf'],
    });
    expect(enriched.name).toBe('Compliance Summary Report');
    expect(enriched.presentation.bestUsedFor.length).toBeGreaterThan(0);
    expect(enriched.displayExportGrade).toBe('Executive Overview');
  });

  it('sorts executive reports before evidentiary archive', () => {
    const sorted = sortReportsForCatalog([
      { id: 'audit_evidence_pack' },
      { id: 'compliance_summary' },
      { id: 'requirements' },
    ]);
    expect(sorted.map((r) => r.id)).toEqual(['compliance_summary', 'requirements', 'audit_evidence_pack']);
  });

  it('marks specialty reports not for generic download', () => {
    expect(isSpecialtyReport('evidence_readiness')).toBe(true);
    expect(isSpecialtyReport('compliance_summary')).toBe(false);
  });

  it('uses canonical filename patterns', () => {
    expect(canonicalReportFilename('compliance_summary', 'csv')).toMatch(/^compliance_summary_/);
    expect(canonicalReportFilename('requirements', 'pdf')).toMatch(/^requirements_report_/);
    expect(canonicalReportFilename('monthly_digest', 'pdf')).toMatch(/^monthly-operations-intelligence-digest-/);
  });

  it('aligns scheduled report labels with catalog names', () => {
    expect(operationalLabelForToken('compliance_summary')).toBe('Compliance Summary Report');
    expect(operationalLabelForToken('requirements')).toBe('Requirements Report');
  });
});
