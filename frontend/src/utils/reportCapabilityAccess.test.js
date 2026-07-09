import {
  evaluateReportCapabilitiesFromMap,
  getCapabilityDeniedMessage,
  isCapabilityDeniedApiError,
  REPORT_CAPABILITY,
  REPORT_LIFECYCLE_GRANT_FIXTURES,
  reportCapabilityAllowedForGrant,
} from './reportCapabilityAccess';
import { GRANT_DENY, GRANT_LIMITED, GRANT_READ } from './capabilityRuntime';

describe('reportCapabilityAccess', () => {
  it('evaluates ACTIVE lifecycle grants for view, download, and write actions', () => {
    const flags = evaluateReportCapabilitiesFromMap(REPORT_LIFECYCLE_GRANT_FIXTURES.ACTIVE);
    expect(flags.canViewReports).toBe(true);
    expect(flags.canDownloadReports).toBe(true);
    expect(flags.canGeneratePdf).toBe(true);
    expect(flags.canGenerateCsv).toBe(true);
    expect(flags.canScheduleReportsWrite).toBe(true);
    expect(flags.canAuditPackWrite).toBe(true);
  });

  it('evaluates READ_ONLY lifecycle — read permitted, write denied', () => {
    const flags = evaluateReportCapabilitiesFromMap(REPORT_LIFECYCLE_GRANT_FIXTURES.READ_ONLY);
    expect(flags.canViewReports).toBe(true);
    expect(flags.canDownloadReports).toBe(true);
    expect(flags.canGeneratePdf).toBe(false);
    expect(flags.canGenerateCsv).toBe(false);
    expect(flags.canScheduleReportsWrite).toBe(false);
    expect(flags.canAuditPackWrite).toBe(false);
  });

  it('evaluates SUSPENDED lifecycle — all report access denied', () => {
    const flags = evaluateReportCapabilitiesFromMap(REPORT_LIFECYCLE_GRANT_FIXTURES.SUSPENDED);
    expect(flags.canViewReports).toBe(false);
    expect(flags.canDownloadReports).toBe(false);
    expect(flags.canGeneratePdf).toBe(false);
    expect(flags.canGenerateCsv).toBe(false);
  });

  it('matches backend read/write grant rules for LIMITED', () => {
    expect(reportCapabilityAllowedForGrant(REPORT_CAPABILITY.VIEW, GRANT_READ, 'read')).toBe(true);
    expect(reportCapabilityAllowedForGrant(REPORT_CAPABILITY.VIEW, GRANT_READ, 'write')).toBe(false);
    expect(reportCapabilityAllowedForGrant(REPORT_CAPABILITY.GENERATE_PDF, GRANT_LIMITED, 'write')).toBe(true);
    expect(reportCapabilityAllowedForGrant(REPORT_CAPABILITY.GENERATE_PDF, GRANT_DENY, 'write')).toBe(false);
  });

  it('parses capability_denied API payloads', () => {
    const error = {
      response: {
        data: {
          detail: {
            error: 'capability_denied',
            message: 'Report generation is not available.',
            capability_id: REPORT_CAPABILITY.GENERATE_PDF,
          },
        },
      },
    };
    expect(isCapabilityDeniedApiError(error)).toBe(true);
    expect(getCapabilityDeniedMessage(error)).toBe('Report generation is not available.');
  });
});
