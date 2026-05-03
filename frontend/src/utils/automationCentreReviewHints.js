/**
 * Job-aware copy for Automation Centre degraded/failed "(review)" tooltips.
 * Delivery-style jobs may reference Message logs; queue workers must not imply that path.
 */

/** Jobs with Message logs drill-down in Automation Centre */
export const AUTOMATION_CENTRE_MESSAGE_LOGS_JOBS = new Set([
  'daily_reminders',
  'monthly_digest',
  'pending_verification_digest',
  'compliance_check_morning',
  'compliance_check_evening',
  'scheduled_reports',
]);

/**
 * @param {string} jobName
 * @returns {string} title attribute for degraded/failed review hint
 */
export function getAutomationCentreDegradedReviewTitle(jobName) {
  if (AUTOMATION_CENTRE_MESSAGE_LOGS_JOBS.has(jobName)) {
    return (
      'Review outcome_metrics and Message logs; act if failures repeat or key notifications are affected.'
    );
  }
  if (jobName === 'compliance_recalc_worker') {
    return 'Review queue failures and audit logs; act if failures repeat.';
  }
  return 'Review outcome_metrics and related logs; act if failures repeat.';
}
