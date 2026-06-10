/**
 * Post-convergence reporting UX catalog — presentation only.
 * Maps report class IDs to purpose, audience, export-grade taxonomy, and ecosystem roles.
 * Does not change API payloads or backend report semantics.
 */

/** @typedef {'evidentiary'|'readiness'|'intelligence'|'executive'|'operational'|'system'} ReportEcosystemGroup */

export const EXPORT_GRADE_TAXONOMY = {
  EVIDENTIARY_ARCHIVE: 'Evidentiary Archive',
  OPERATIONAL_READINESS: 'Operational Readiness',
  PORTFOLIO_INTELLIGENCE: 'Portfolio Intelligence',
  EXECUTIVE_OVERVIEW: 'Executive Overview',
  OPERATIONAL_MANAGEMENT: 'Operational Management',
  SYSTEM_AUDIT: 'System Audit',
};

export const FORMAT_GUIDANCE = {
  pdf: 'PDF — presentation and governance view for review and sharing.',
  csv: 'CSV — structured operational export for analysis and external systems.',
  zip: 'ZIP — governed archive bundle with manifest and checksums.',
};

export const REPORT_ECOSYSTEM_NOTE =
  'Monthly Digest surfaces trends · Evidence Readiness identifies remediation · Requirements Report tracks obligations · Compliance Summary explains posture · Audit Evidence Pack preserves evidence.';

/**
 * Canonical presentation metadata per report class.
 * Keys match backend catalog `id` values and notification tokens where applicable.
 */
export const REPORT_CATALOG = {
  audit_evidence_pack: {
    canonicalName: 'Audit Evidence Pack',
    purpose: 'Immutable evidentiary archive for regulatory, insurer, solicitor, or tribunal review.',
    audience: 'External reviewers, solicitors, insurers, regulators',
    exportGrade: EXPORT_GRADE_TAXONOMY.EVIDENTIARY_ARCHIVE,
    bestUsedFor: ['legal evidence support', 'insurer review', 'tribunal submission', 'third-party audit'],
    ecosystemGroup: 'evidentiary',
    ecosystemRole: 'Preserves governed evidence at a point in time.',
    governanceNote: 'Frozen deterministic snapshot with manifest checksums. Re-download returns the same bytes.',
    sortOrder: 50,
  },
  evidence_readiness: {
    canonicalName: 'Evidence Readiness Report',
    purpose: 'Operational audit-preparedness and remediation assessment.',
    audience: 'Compliance managers, internal audit prep',
    exportGrade: EXPORT_GRADE_TAXONOMY.OPERATIONAL_READINESS,
    bestUsedFor: ['internal audit prep', 'remediation planning', 'evidence gap review'],
    ecosystemGroup: 'readiness',
    ecosystemRole: 'Identifies what to fix before external review.',
    governanceNote: 'Point-in-time snapshot. Immutable copies available in report history.',
    sortOrder: 30,
  },
  monthly_digest: {
    canonicalName: 'Monthly Operations Intelligence Digest',
    purpose: 'Recurring portfolio intelligence and operational monitoring summary.',
    audience: 'Portfolio owners, operations leads',
    exportGrade: EXPORT_GRADE_TAXONOMY.PORTFOLIO_INTELLIGENCE,
    bestUsedFor: ['monthly oversight', 'compliance monitoring', 'portfolio trend review'],
    ecosystemGroup: 'intelligence',
    ecosystemRole: 'Surfaces trends and operational signals over time.',
    governanceNote: 'Informational intelligence — not an evidentiary archive.',
    sortOrder: 40,
  },
  requirements: {
    canonicalName: 'Requirements Report',
    purpose: 'Operational obligation tracking and action-management report.',
    audience: 'Property managers, compliance operators',
    exportGrade: EXPORT_GRADE_TAXONOMY.OPERATIONAL_MANAGEMENT,
    bestUsedFor: ['operational management', 'obligation tracking', 'renewal scheduling'],
    ecosystemGroup: 'operational',
    ecosystemRole: 'Tracks obligations and prioritises day-to-day actions.',
    governanceNote: 'Point-in-time operational export. Server PDF is authoritative.',
    sortOrder: 20,
  },
  compliance_summary: {
    canonicalName: 'Compliance Summary Report',
    purpose: 'Executive compliance posture and portfolio overview.',
    audience: 'Landlords, lenders, senior portfolio managers',
    exportGrade: EXPORT_GRADE_TAXONOMY.EXECUTIVE_OVERVIEW,
    bestUsedFor: ['compliance monitoring', 'insurer review', 'executive briefing'],
    ecosystemGroup: 'executive',
    ecosystemRole: 'Explains portfolio posture at the generation boundary.',
    governanceNote: 'CVP headline uses persisted scores; export is a point-in-time snapshot.',
    sortOrder: 10,
  },
  audit_logs: {
    canonicalName: 'Audit Log Extract',
    purpose: 'System activity trail for administrative compliance review.',
    audience: 'Administrators, compliance officers',
    exportGrade: EXPORT_GRADE_TAXONOMY.SYSTEM_AUDIT,
    bestUsedFor: ['internal audit prep', 'activity review'],
    ecosystemGroup: 'system',
    ecosystemRole: 'Supports activity traceability.',
    governanceNote: 'Operational system log export.',
    sortOrder: 60,
  },
};

export const ECOSYSTEM_GROUP_LABELS = {
  executive: 'Executive overview',
  operational: 'Operational management',
  readiness: 'Audit preparedness',
  intelligence: 'Portfolio intelligence',
  evidentiary: 'Evidentiary archive',
  system: 'System exports',
};

/** Legacy / internal tokens that must not appear in user-facing copy */
const FORBIDDEN_LEAK_PATTERN =
  /UNKNOWN_DATE|workflow_class|SELF_RECORDED|SATISFIED_UNVERIFIED|evidence_state|client_lifecycle|triage at a glance/i;

/**
 * @param {string} id
 * @returns {typeof REPORT_CATALOG[string]|null}
 */
export function getReportPresentation(id) {
  return REPORT_CATALOG[id] || null;
}

/**
 * Merge API catalog row with presentation metadata.
 * @param {Record<string, unknown>} apiReport
 */
export function enrichReportFromApi(apiReport) {
  const id = String(apiReport?.id || '');
  const pres = getReportPresentation(id) || {};
  const gradeFromApi = apiReport.export_grade_label;
  return {
    ...apiReport,
    name: pres.canonicalName || apiReport.name,
    description: pres.purpose || apiReport.description,
    presentation: pres,
    displayExportGrade: pres.exportGrade || gradeFromApi || null,
  };
}

/**
 * @param {Array<Record<string, unknown>>} reports
 * @returns {Array<Record<string, unknown>>}
 */
export function sortReportsForCatalog(reports) {
  return [...reports].sort((a, b) => {
    const ao = getReportPresentation(a.id)?.sortOrder ?? 99;
    const bo = getReportPresentation(b.id)?.sortOrder ?? 99;
    return ao - bo;
  });
}

/**
 * Reports handled by dedicated UI flows (not generic GET download).
 */
export const SPECIALTY_REPORT_IDS = new Set(['evidence_readiness', 'audit_evidence_pack']);

/**
 * @param {string} id
 */
export function isSpecialtyReport(id) {
  return SPECIALTY_REPORT_IDS.has(id);
}

/**
 * @param {string} text
 * @returns {boolean}
 */
export function assertClientReportCopySafe(text) {
  if (!text || typeof text !== 'string') return true;
  return !FORBIDDEN_LEAK_PATTERN.test(text);
}

/**
 * @param {string} [contentDisposition]
 * @param {string} fallback
 */
export function filenameFromContentDisposition(contentDisposition, fallback) {
  if (!contentDisposition) return fallback;
  const match = contentDisposition.match(/filename\*?=(?:UTF-8''|"?)([^";]+)"?/i);
  if (match) {
    try {
      return decodeURIComponent(match[1].replace(/"/g, ''));
    } catch {
      return match[1].replace(/"/g, '');
    }
  }
  return fallback;
}

/**
 * Canonical download filename fallbacks aligned with server naming.
 * @param {string} reportId
 * @param {'csv'|'pdf'|'zip'} format
 */
export function canonicalReportFilename(reportId, format) {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '').slice(0, 13);
  const names = {
    compliance_summary: { csv: `compliance_summary_${stamp}.csv`, pdf: `compliance_summary_${stamp}.pdf` },
    requirements: { csv: `requirements_report_${stamp}.csv`, pdf: `requirements_report_${stamp}.pdf` },
    evidence_readiness: { pdf: `evidence_readiness_portfolio_${date}.pdf` },
    audit_evidence_pack: { zip: `audit_evidence_pack_${date}.zip` },
    monthly_digest: { pdf: `monthly-operations-intelligence-digest-${date}.pdf` },
    audit_logs: { csv: `audit_log_${stamp}.csv`, pdf: `audit_log_${stamp}.pdf` },
  };
  return names[reportId]?.[format] || `report_${reportId}_${date}.${format}`;
}

/**
 * Card visual tier — restrained hierarchy only.
 * @param {string} ecosystemGroup
 */
export function reportCardTierClass(ecosystemGroup) {
  switch (ecosystemGroup) {
    case 'evidentiary':
      return 'border-slate-300 bg-slate-50/30';
    case 'executive':
      return 'border-midnight-blue/20 bg-white';
    case 'intelligence':
      return 'border-gray-200 bg-gray-50/40';
    default:
      return 'border-gray-200 bg-white';
  }
}
