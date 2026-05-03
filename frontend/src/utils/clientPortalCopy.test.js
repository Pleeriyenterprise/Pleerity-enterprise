/**
 * @jest-environment jsdom
 */
import { PORTAL_COPY } from './clientPortalCopy';

describe('clientPortalCopy risk terminology', () => {
  it('uses risk signal vocabulary instead of ambiguous flagged-issues wording', () => {
    expect(PORTAL_COPY.riskSignal).toMatch(/risk signal/i);
    expect(PORTAL_COPY.riskSignalsActiveHeading).toMatch(/risk signals/i);
    expect(PORTAL_COPY.riskSignal.toLowerCase()).not.toContain('flagged');
    expect(PORTAL_COPY.riskSignalsActiveHeading.toLowerCase()).not.toContain('flagged');
  });

  it('uses operational CTA wording that does not imply compliance restoration', () => {
    expect(PORTAL_COPY.startMaintenanceJob).toMatch(/maintenance job/i);
    expect(PORTAL_COPY.createComplianceJob).toMatch(/compliance job/i);
    expect(PORTAL_COPY.addWorkOrder).toBe(PORTAL_COPY.startMaintenanceJob);
    expect(PORTAL_COPY.reviewRiskSignal).toMatch(/risk signal/i);
    expect(PORTAL_COPY.submitMaintenanceReport).toMatch(/submit/i);
  });
});
