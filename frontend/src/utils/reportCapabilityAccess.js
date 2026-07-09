import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import {
  evaluateCapabilityGrant,
  extractCapabilityDeniedFromError,
  GRANT_ALLOW,
  GRANT_DENY,
  GRANT_LIMITED,
  GRANT_READ,
  isGrantActionAllowed,
} from './capabilityRuntime';

/** Governed Runtime Contract capability ids for the Reports domain. */
export const REPORT_CAPABILITY = {
  VIEW: 'CAP_REPORT_VIEW',
  DOWNLOAD: 'CAP_REPORT_DOWNLOAD',
  GENERATE_PDF: 'CAP_REPORT_GENERATE_PDF',
  GENERATE_CSV: 'CAP_REPORT_GENERATE_CSV',
  SCHEDULE: 'CAP_REPORT_SCHEDULE',
  AUDIT_PACK: 'CAP_REPORT_AUDIT_PACK',
  OPS_RENT: 'CAP_OPS_RENT',
};

/**
 * Runtime Contract capability consumption for Reports UI.
 */
export function useReportCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewReports: capabilityAllowed(REPORT_CAPABILITY.VIEW, 'read'),
      canDownloadReports: capabilityAllowed(REPORT_CAPABILITY.DOWNLOAD, 'read'),
      canGeneratePdf: capabilityAllowed(REPORT_CAPABILITY.GENERATE_PDF, 'write'),
      canGenerateCsv: capabilityAllowed(REPORT_CAPABILITY.GENERATE_CSV, 'write'),
      canScheduleReportsRead: capabilityAllowed(REPORT_CAPABILITY.SCHEDULE, 'read'),
      canScheduleReportsWrite: capabilityAllowed(REPORT_CAPABILITY.SCHEDULE, 'write'),
      canAuditPackRead: capabilityAllowed(REPORT_CAPABILITY.AUDIT_PACK, 'read'),
      canAuditPackWrite: capabilityAllowed(REPORT_CAPABILITY.AUDIT_PACK, 'write'),
      canViewRentOperationsSummary: capabilityAllowed(REPORT_CAPABILITY.OPS_RENT, 'read'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function getCapabilityDeniedMessage(error, fallback = 'Action not permitted') {
  const detail = extractCapabilityDeniedFromError(error);
  return detail?.message || null;
}

export function isCapabilityDeniedApiError(error) {
  return Boolean(extractCapabilityDeniedFromError(error));
}

/**
 * Lifecycle grant expectations for report capabilities (mirrors backend runtime matrix semantics).
 * Used by tests — READ/ALLOW/LIMITED permit read; ALLOW/LIMITED permit write.
 */
export function reportCapabilityAllowedForGrant(capabilityId, grant, action) {
  return isGrantActionAllowed(grant, action);
}

export const REPORT_LIFECYCLE_GRANT_FIXTURES = {
  ACTIVE: {
    CAP_REPORT_VIEW: GRANT_ALLOW,
    CAP_REPORT_DOWNLOAD: GRANT_ALLOW,
    CAP_REPORT_GENERATE_PDF: GRANT_ALLOW,
    CAP_REPORT_GENERATE_CSV: GRANT_ALLOW,
    CAP_REPORT_SCHEDULE: GRANT_ALLOW,
    CAP_REPORT_AUDIT_PACK: GRANT_ALLOW,
  },
  READ_ONLY: {
    CAP_REPORT_VIEW: GRANT_READ,
    CAP_REPORT_DOWNLOAD: GRANT_READ,
    CAP_REPORT_GENERATE_PDF: GRANT_DENY,
    CAP_REPORT_GENERATE_CSV: GRANT_DENY,
    CAP_REPORT_SCHEDULE: GRANT_DENY,
    CAP_REPORT_AUDIT_PACK: GRANT_DENY,
  },
  SUSPENDED: {
    CAP_REPORT_VIEW: GRANT_DENY,
    CAP_REPORT_DOWNLOAD: GRANT_DENY,
    CAP_REPORT_GENERATE_PDF: GRANT_DENY,
    CAP_REPORT_GENERATE_CSV: GRANT_DENY,
    CAP_REPORT_SCHEDULE: GRANT_DENY,
    CAP_REPORT_AUDIT_PACK: GRANT_DENY,
  },
};

export function evaluateReportCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewReports: evaluateCapabilityGrant(caps, REPORT_CAPABILITY.VIEW, 'read').allowed,
    canDownloadReports: evaluateCapabilityGrant(caps, REPORT_CAPABILITY.DOWNLOAD, 'read').allowed,
    canGeneratePdf: evaluateCapabilityGrant(caps, REPORT_CAPABILITY.GENERATE_PDF, 'write').allowed,
    canGenerateCsv: evaluateCapabilityGrant(caps, REPORT_CAPABILITY.GENERATE_CSV, 'write').allowed,
    canScheduleReportsRead: evaluateCapabilityGrant(caps, REPORT_CAPABILITY.SCHEDULE, 'read').allowed,
    canScheduleReportsWrite: evaluateCapabilityGrant(caps, REPORT_CAPABILITY.SCHEDULE, 'write').allowed,
    canAuditPackRead: evaluateCapabilityGrant(caps, REPORT_CAPABILITY.AUDIT_PACK, 'read').allowed,
    canAuditPackWrite: evaluateCapabilityGrant(caps, REPORT_CAPABILITY.AUDIT_PACK, 'write').allowed,
  };
}
