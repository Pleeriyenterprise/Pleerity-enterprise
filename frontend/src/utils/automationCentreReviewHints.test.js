import {
  getAutomationCentreDegradedReviewTitle,
  AUTOMATION_CENTRE_MESSAGE_LOGS_JOBS,
} from './automationCentreReviewHints';

describe('getAutomationCentreDegradedReviewTitle', () => {
  it('mentions Message logs for delivery-style jobs', () => {
    const t = getAutomationCentreDegradedReviewTitle('daily_reminders');
    expect(t).toMatch(/Message logs/i);
    expect(AUTOMATION_CENTRE_MESSAGE_LOGS_JOBS.has('daily_reminders')).toBe(true);
  });

  it('does not mention Message logs for compliance_recalc_worker', () => {
    const t = getAutomationCentreDegradedReviewTitle('compliance_recalc_worker');
    expect(t).not.toMatch(/message logs/i);
    expect(t).toMatch(/queue failures and audit logs/i);
  });

  it('uses generic wording for other jobs', () => {
    const t = getAutomationCentreDegradedReviewTitle('sla_watchdog');
    expect(t).not.toMatch(/message logs/i);
    expect(t).toMatch(/outcome_metrics and related logs/i);
  });
});
